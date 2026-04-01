---
status: draft
branch:
created: 2026-04-01T06:41:37-07:00
completed:
pr:
---

# Add type checker to proj-template

## Context

The template currently has ruff for linting/formatting and pytest for testing, but no static type checking. Adding a type checker to the template means every new project scaffolded from it gets type checking out of the box — in pre-commit hooks, CI, and dev dependencies.

## Options comparison

| | mypy | Pyright | Pyrefly | ty |
|---|---|---|---|---|
| **Version** | 1.20.0 | 1.1.408 | 0.59.0 (beta) | beta |
| **Language** | Python | TypeScript | Rust | Rust |
| **Speed** | Baseline (slowest) | ~5x faster | ~14x faster | 10-60x faster |
| **Typing conformance** | ~57% | Highest | ~58% | ~15% |
| **Maturity** | Stable, 10+ years | Stable, frequent releases | Beta | Beta |
| **pyproject.toml** | `[tool.mypy]` | `[tool.pyright]` | `[tool.pyrefly]` | `[tool.ty]` |
| **Pre-commit hook** | Official (fiddly) | Good (pyright-python) | Official | No official hook |
| **Runtime dep** | None | Node.js | None | None |
| **uv integration** | Works | Works | Works | Best (same ecosystem) |
| **Python 3.14** | Yes (1.20) | Yes | Yes | Yes |

### Pytype (Google) — eliminated

Sunset by Google. Python 3.12 is the last supported version. Not viable.

### mypy — conservative choice

Largest ecosystem and most third-party stubs. But slowest, lowest conformance for its age, and pre-commit integration has known issues (exclude patterns ignored when pre-commit passes individual files, requires listing `additional_dependencies` for stubs).

### Pyright — strongest today

Highest typing spec conformance, good speed, solid pre-commit hook via `pyright-python`, excellent VS Code/Pylance integration. Downside: requires Node.js runtime (not pure Python). `--verifytypes` is useful for library authors.

### Pyrefly — fast but beta

14x faster than mypy, official pre-commit hook, config migration from mypy/pyright via `pyrefly init`. But beta maturity, ~58% conformance, known bugs, and pre-commit hook silently skips files outside `project-includes`.

### ty — fastest but earliest

Same Astral ecosystem as ruff and uv (natural fit). Extraordinary incremental speed (~5ms rechecks). But lowest conformance (~15%), no official pre-commit hook, and OpenAI's acquisition of Astral (March 2026) introduces governance uncertainty.

## Recommendation

**Pyright** is the strongest choice for a project template today:

1. **Highest conformance** — catches the most real issues
2. **Stable and battle-tested** — won't produce false positives that frustrate new project authors
3. **Good pre-commit story** — `pyright-python` hook works cleanly
4. **VS Code integration** — Pylance uses Pyright, so editor and CI agree
5. **Low switching cost** — if ty matures and becomes the standard, migrating from Pyright is straightforward (both use pyproject.toml config, similar strictness levels)

The Node.js dependency is the main drawback, but `pyright` installs it automatically via the Python wrapper package — users don't need to manage Node themselves.

**Alternative worth considering:** wait for ty to stabilize (targeting 2026 stable release). If the Astral ecosystem is the long-term bet, starting with Pyright now and switching to ty later is low-friction. Or start with Pyrefly if Meta's investment and speed matter more than conformance.

## Plan

### 1. Add Pyright to dev dependencies

In `template/pyproject.toml`:

```toml
[project.optional-dependencies]
dev = [
    "pre-commit",
    "pyright",
    "pytest>=9.0.2",
    "pytest-cov",
    "ruff",
]
```

### 2. Add Pyright configuration

In `template/pyproject.toml`:

```toml
[tool.pyright]
pythonVersion = "3.11"
typeCheckingMode = "standard"
```

Use `"standard"` mode (not `"strict"`) — strict is too noisy for a template that scaffolds general-purpose projects. Target 3.11 as the minimum supported version (matches the existing `requires-python = ">=3.11"`).

### 3. Add pre-commit hook

In `template/.pre-commit-config.yaml`, add after the ruff hooks:

```yaml
- repo: https://github.com/RobertCraigie/pyright-python
  rev: v1.1.408
  hooks:
    - id: pyright
```

### 4. Add CI step

In `template/.github/workflows/test.yml`, add a type check step after ruff checks:

```yaml
- name: Type check
  run: uv run pyright
```

### 5. Update documentation

- Update `template/CLAUDE.md` to mention type checking in the development workflow
- Update the root `README.md` if it documents the template's tooling

### 6. Update proj-init.sh

Verify the scaffold script doesn't need changes — it already runs `uv sync --all-groups` which will install the new dev dependency.

### 7. Test

- Scaffold a new project from the updated template
- Verify pyright passes on the template's default code
- Verify pre-commit hook runs
- Verify CI workflow runs type checking
