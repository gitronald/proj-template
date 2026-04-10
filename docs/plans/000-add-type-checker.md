---
status: done
branch: feature/add-type-checker
created: 2026-04-01T06:41:37-07:00
completed: 2026-04-09T13:57:50-07:00
pr: https://github.com/gitronald/proj-template/pull/4
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

### Pyright vs Pyrefly — detailed comparison

**Conformance trajectory:** Pyrefly improved from 39% (alpha, May 2025) to ~58% (beta, Nov 2025) — a fast trajectory, but still behind Pyright which leads all checkers on the typing spec conformance suite.

**What Pyright catches that Pyrefly misses:**

- **ParamSpec and TypeVarTuple** — advanced callable generics (PEP 612, PEP 646). Pyright has the most complete implementation; Pyrefly's support is partial.
- **Complex `@overload` resolution** — Pyright is stricter about matching overload signatures with union narrowing across multiple dispatch paths.
- **Generic protocols** — edge cases in structural subtyping with parameterized protocols. Pyright resolves these more robustly.
- **TypeGuard / TypeIs narrowing** — newer type narrowing constructs (PEP 742). Pyright's narrowing is more thorough in branching logic.
- **Recursive type aliases** — deeply nested `TypeAlias` recursion. Pyright handles these without choking.
- **`--verifytypes`** — Pyright offers a library completeness checker that audits public API type coverage, useful for package authors. Pyrefly has no equivalent.

**What Pyrefly catches that Pyright may not:**

- **Aggressive inference on untyped code** — Pyrefly's flow-sensitive analysis infers types more aggressively even without annotations, surfacing bugs in code that Pyright's more conservative inference leaves unchecked. This is a double-edged sword — more detection but also more false positives on valid patterns.

**Known Pyrefly limitations (beta):**

- Pre-commit hook silently skips files outside `project-includes` — must be configured carefully or files get no checking at all.
- Incremental/editor recheck is slow relative to its full-check speed (2.38s for a single-file edit in PyTorch vs ty's 4.7ms) — the speed advantage is in cold full-project checks, not IDE feedback loops.
- Django, Pydantic, and Jupyter support listed as "in progress" — third-party framework stubs are less complete than Pyright's ecosystem.
- Config migration from mypy/pyright (`pyrefly init`) exists but may not cover all options.

**Where they agree:**

Straightforward annotations — function signatures, return types, `Optional` handling, basic generics, `Union` types, `Literal`, `TypedDict` — are caught similarly by both tools. For a typical project scaffolded from a template, most day-to-day type errors land in this category.

**Practical implications for a project template:**

The conformance gap hits hardest on advanced typing patterns that small/medium projects rarely use. For a template, either tool catches the bugs that matter. The real differentiators are: Pyright's maturity and VS Code integration vs Pyrefly's speed (14x) and zero runtime dependencies (no Node.js). If projects spawned from the template grow into typed libraries with complex generics, Pyright's deeper conformance pays off. If they stay as applications with standard annotations, Pyrefly's speed and simplicity are advantages.

### ty — fastest but earliest

Same Astral ecosystem as ruff and uv (natural fit). Extraordinary incremental speed (~5ms rechecks). But lowest conformance (~15%), no official pre-commit hook, and OpenAI's acquisition of Astral (March 2026) introduces governance uncertainty.

## Recommendation

**Pyrefly** — fast, no runtime dependencies, and sufficient conformance for the template's use case:

1. **Speed** — 14x faster than mypy, no Node.js dependency (pure Python install via uv)
2. **Good enough conformance** — the ~58% gaps are in advanced generics, ParamSpec, and recursive aliases that template projects won't exercise
3. **Official pre-commit hook** — `facebook/pyrefly-pre-commit`, though `project-includes` must be configured correctly
4. **Fast conformance trajectory** — 39% to 58% in 6 months of active Meta investment
5. **Low switching cost** — pyproject.toml config, standard CLI; migrating to Pyright or ty later is straightforward

**Tradeoffs accepted:** beta maturity, less complete third-party stub coverage, no `--verifytypes` equivalent for library authors. Individual projects can swap to Pyright if they outgrow Pyrefly's coverage.

## Alternative plan: Pyright

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

## Plan: Pyrefly

### 1. Add Pyrefly to dev dependencies

In `template/pyproject.toml`:

```toml
[project.optional-dependencies]
dev = [
    "pre-commit",
    "pyrefly",
    "pytest>=9.0.2",
    "pytest-cov",
    "ruff",
]
```

### 2. Add Pyrefly configuration

In `template/pyproject.toml`:

```toml
[tool.pyrefly]
python-version = "3.11"
project-includes = ["."]
```

Pyrefly defaults to checking all files under `project-includes`. No strict/standard toggle — error levels are controlled per-rule via `[tool.pyrefly.errors]` if needed.

### 3. Add pre-commit hook

In `template/.pre-commit-config.yaml`, add after the ruff hooks:

```yaml
- repo: https://github.com/facebook/pyrefly-pre-commit
  rev: v0.59.0
  hooks:
    - id: pyrefly
```

**Note:** The hook silently skips files outside `project-includes`, so ensure the config covers the package directory. Test this after setup.

### 4. Add CI step

In `template/.github/workflows/test.yml`, add a type check step after ruff checks:

```yaml
- name: Type check
  run: uv run pyrefly check
```

### 5. Update documentation

Same as Pyright plan — update `template/CLAUDE.md` and root `README.md`.

### 6. Update proj-init.sh

Same as Pyright plan — no changes expected.

### 7. Test

- Scaffold a new project from the updated template
- Verify pyrefly passes on the template's default code
- Verify pre-commit hook runs (and doesn't silently skip files)
- Verify CI workflow runs type checking
- Check for false positives — beta tooling may flag valid code

## Log

### 2026-04-09

- Implemented pyrefly plan: added dev dependency, pyproject.toml config, pre-commit hook, CI step, and docs
- Created PR #4 (https://github.com/gitronald/proj-template/pull/4) into dev

## Retrospective

Went with Pyrefly over Pyright based on speed (14x over mypy), no Node.js dependency, and sufficient conformance for template-scaffolded projects. The alternative Pyright plan is documented above if a project outgrows Pyrefly's coverage. Implementation was straightforward — four files touched in the template, no changes needed to `proj-init.sh` since `uv sync --all-groups` picks up the new dependency automatically. The main thing to watch going forward is Pyrefly's beta stability and whether the pre-commit hook's `project-includes` behavior causes silent skips in real projects.
