---
status: draft
branch: feature/upgrade-lint-typecheck
created: 2026-05-25T13:10:08-07:00
completed:
pr:
---

# Upgrade lint and type-check tooling for pyrefly v1.0 with agentic integration

## Context

Two upstream releases prompt this update:

- **pyrefly v1.0.0** (May 2026) — the first stable release of Meta's Python type checker. It is now production-ready (default on Instagram, adopted by PyTorch/NumPy/pandas-stubs/JAX), reaches >90% conformance with the typing spec (up from 70% at beta), and ships materially fewer false positives. v1.0 also introduces **named config presets**, **coverage reporting**, and **baseline files**, plus published guidance for using pyrefly inside agentic coding loops.
- **ruff** — the template pins `ruff-pre-commit` at `v0.15.5`; latest is `v0.15.14`. This is a routine within-`0.15.x` patch bump (bug fixes, rule/stub updates), not a behavior overhaul.

The template currently wires both tools through pre-commit and CI but has **no agentic integration** — nothing makes an in-editor agent run the checks before finishing a task. The pyrefly team's [agentic-loop guidance](https://pyrefly.org/blog/pyrefly-agentic-loop/) recommends closing that gap with a `Stop` hook plus an `AGENTS.md`/`CLAUDE.md` directive (noting a skill alone is insufficient).

### Current template state (baseline)

- `template/pyproject.toml`
  - dev group: `pyrefly` and `ruff` are **unpinned**.
  - `[tool.ruff.lint]` selects `F, E, W, I, UP`; `target-version = "py311"`.
  - `[tool.pyrefly]`: `python-version = "3.11"`, `project-includes = ["."]` — **no preset set**, so v1.0 silently applies the lightweight `basic` preset.
- `template/.pre-commit-config.yaml` — `ruff-pre-commit` at `v0.15.5` (ruff-format + ruff `--fix`); a local `pyrefly-check` hook running `uv run pyrefly check`.
- `template/.github/workflows/test.yml` — runs `ruff check`, `ruff format --check`, `pyrefly check`, `pytest` across Python 3.11–3.14.
- `template/.claude/settings.local.json` — permissions only; **no hooks**.
- `template/CLAUDE.md` — Development section mentions lint/type-check via pre-commit, but no directive to run them before completing a task.
- `proj-init.sh` copies all of `template/` via `rsync -a` (including `.claude/`), so any new file added under `template/` automatically ships to scaffolded projects.
- Root `docs/guides/` holds the template's own reference guides (`pre-commit.md`, `trusted-publishers.md`); `template/docs/guides/` is empty (`.gitkeep`).

### Decisions (confirmed with user)

- **Preset: `strict`** — the template should model good typing hygiene; strict adds checks on top of default and discourages `Any`.
- **Agentic integration: hook + directive + skill** — committed `Stop` hook, a `CLAUDE.md`/`AGENTS.md` directive, and a reusable skill that codifies the lint/type-check workflow.

## Plan

### 1. Version bumps

- `template/.pre-commit-config.yaml`: bump `astral-sh/ruff-pre-commit` `rev` from `v0.15.5` to `v0.15.14`.
- `template/pyproject.toml` dev group: pin floors so scaffolded projects resolve the intended majors —
  - `pyrefly>=1.0.0` (was bare `pyrefly`; pre-1.0 alpha/beta resolutions are no longer desirable).
  - `ruff>=0.15` (was bare `ruff`).
  - **Rationale for pinning pyrefly:** pyrefly explicitly does **not** follow strict semver — any release (minor or patch) may introduce new type errors or breaking changes. A floor of `>=1.0.0` keeps new projects on the stable line; the committed `uv.lock` (created at scaffold time) pins the exact version for reproducibility.

### 2. Adopt pyrefly v1.0 config in `template/pyproject.toml`

Update `[tool.pyrefly]`:

```toml
[tool.pyrefly]
preset = "strict"
python-version = "3.11"
project-includes = ["."]
project-excludes = ["**/__pycache__", "**/.venv"]
```

- `preset = "strict"` is the headline change — opts new projects into the strictest checking by default.
- Keep `python-version = "3.11"` (the floor of `requires-python = ">=3.11"`) so pyrefly checks compatibility against the lowest supported interpreter, independent of the `3.14` dev `.python-version`.
- Add `project-excludes` for `__pycache__`/`.venv` hygiene (v1.0 config key).
- Note: v1.0 config keys are hyphenated (`python-version`, `project-includes`, `project-excludes`, `preset`). Verify against `pyrefly init` output during implementation since the template hand-maintains this block rather than generating it.

### 3. Agentic integration

**3a. Committed Stop hook** — add `template/.claude/settings.json` (a new, shared, committed file — distinct from the existing `settings.local.json` which stays for personal permissions) with a `Stop` hook that runs the checks and surfaces failures back to the agent:

- Command: lint + type-check, non-mutating — `uv run ruff check . && uv run pyrefly check`. (Use `ruff check`, not `ruff format`, in the hook — auto-formatting/mutation stays in pre-commit; the Stop hook only *reports*.)
- Must redirect output to **stderr** and exit **2** so Claude Code reads the failure and acts on it.
- Use Claude Code's **actual** Stop-hook schema (matcher object wrapping a nested `hooks` array), not the simplified snippet from the blog post. Verify the exact shape against current Claude Code docs during implementation. Expected shape:

  ```json
  {
    "hooks": {
      "Stop": [
        {
          "hooks": [
            {
              "type": "command",
              "command": "uv run ruff check . >&2 && uv run pyrefly check >&2 || exit 2",
              "timeout": 60
            }
          ]
        }
      ]
    }
  }
  ```

  (Flagged area — confirm the `|| exit 2` precedence/redirection actually propagates a non-zero ruff failure too; may need a small wrapper or grouped command.)

**3b. Directive in `template/CLAUDE.md`** — add an explicit instruction under Development (and/or a top-level "Before finishing" line) mandating: run `uv run ruff check .` and `uv run pyrefly check` at the project root and fix all reported errors before completing a task. Per pyrefly's guidance this directive is the reliable backstop that a skill alone does not provide. Consider whether scaffolded projects should also get an `AGENTS.md` for editor-agnostic agents (decide during implementation — `CLAUDE.md` is the minimum).

**3c. Reusable skill** — add a skill that codifies the lint + type-check workflow for on-demand invocation (e.g., `lint-and-typecheck`): run ruff format/fix + ruff check, run pyrefly check, interpret pyrefly's output, and apply v1.0 adoption tooling when relevant (`pyrefly suppress`, `pyrefly infer`, baseline files). Decide skill home during implementation: ship inside `template/.claude/skills/` so scaffolded projects inherit it, vs. a user-level skill in `~/.claude/skills/`. Default: ship in the template so the workflow travels with each project. Use `/skill-creator` to author it.

### 4. Guide doc — `docs/guides/lint-and-typecheck.md`

Add a concise reference guide to the **root** `docs/guides/` (alongside `pre-commit.md`), matching that guide's voice ("Projects created from this template include…"). One combined guide covering both tools, with these sections:

- **Overview** — ruff (format + lint) and pyrefly (type check) and how they divide responsibility; how they relate to pre-commit (commit-time), CI (push/PR), and the Stop hook (agent task completion).
- **ruff** — the selected rule sets (`F/E/W/I/UP`), `ruff check`/`ruff format`, `--fix`, and how to extend `select`.
- **pyrefly v1.0** — the preset model (`off`/`basic`/`legacy`/`default`/`strict`) and why the template uses `strict`; core CLI (`pyrefly check`, `init`, `suppress`, `infer`, `report`/coverage JSON); baseline files for incremental adoption; and the **semver caveat** (any version may add errors — pin and upgrade deliberately).
- **Agentic use** — what the Stop hook does and the `CLAUDE.md` directive, linking the [pyrefly agentic-loop post](https://pyrefly.org/blog/pyrefly-agentic-loop/) and the `lint-and-typecheck` skill.
- **Migrating an existing project** — `pyrefly init` to auto-migrate mypy/pyright config; `pyrefly suppress` + baseline to stage adoption.

Cross-link: add the new guide to `docs/README.md`'s Guides section if it enumerates guides, and reference it from `pre-commit.md` where relevant.

### 5. CI alignment (`template/.github/workflows/test.yml`)

- CI already runs `ruff check`, `ruff format --check`, and `pyrefly check` — no structural change needed.
- Confirm the strict preset doesn't break the template's own placeholder package under CI (the `PACKAGE` stub must pass `pyrefly check --preset strict` clean). If the stub trips strict checks, either add minimal annotations to the stub or document the expected first-run cleanup. **This is the main risk** — `strict` on real scaffolded code will surface more errors than `basic`; that is intended, but the template's own sample code must be clean.

### 6. Verify

- Run `uv sync --all-groups` and `uv run pyrefly check` / `uv run ruff check .` against `template/` (or a throwaway scaffold via `proj-init.sh`) to confirm the strict preset and pinned versions resolve and pass.
- Confirm `pre-commit run --all-files` passes with the bumped ruff rev.
- Manually exercise the Stop hook (trigger a deliberate type error, confirm the agent sees the stderr/exit-2 failure).

## Implementation order

1. Version bumps (§1) — low risk, isolated.
2. pyrefly preset + config (§2), then verify the template stub passes `strict` (§5) — resolve any stub fixes here.
3. Stop hook + `settings.json` (§3a) and `CLAUDE.md` directive (§3b).
4. Skill (§3c) via `/skill-creator`.
5. Guide doc (§4).
6. Full verify (§6); update `CHANGELOG.md`; version bump via `stanza release`.

## Open questions / flagged areas

- Exact Claude Code Stop-hook JSON schema and whether the chained `ruff && pyrefly … || exit 2` reliably propagates both failures — verify against current docs (§3a).
- Skill home: ship in `template/.claude/skills/` (travels with projects) vs. user-level (§3c). Leaning template.
- Whether to also add `AGENTS.md` for non-Claude agents (§3b).
- Confirm pyrefly v1.0 TOML key spellings via `pyrefly init` rather than trusting hand-written keys (§2).

