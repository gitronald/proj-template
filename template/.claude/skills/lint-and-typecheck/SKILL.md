---
name: lint-and-typecheck
description: Run and resolve this project's ruff (lint + format) and pyrefly (type check, strict preset) checks. Use whenever lint or type errors need fixing, before finishing a coding task, when interpreting pyrefly output, adopting pyrefly into an existing or legacy codebase, suppressing or inferring types, building a baseline for incremental adoption, or checking type coverage. Trigger even if the user just says "run the checks", "fix the type errors", "clean this up", or mentions ruff or pyrefly by name.
---

# Lint and type-check

This project gates code on two tools: **ruff** (formatting + linting) and
**pyrefly** (type checking on the `strict` preset). Both run in pre-commit and
CI, and a `Stop` hook (`.claude/hooks/lint-typecheck.sh`) re-runs them when an
agent finishes a task. Run them yourself as you work so failures never surprise
you at the gate — the hook is a backstop, not your first signal.

Config lives in `pyproject.toml`: `[tool.ruff]` / `[tool.ruff.lint]` and
`[tool.pyrefly]`. A companion guide with the full reference is at
`docs/guides/lint-and-typecheck.md`.

## Standard workflow

Run from the project root, in this order:

1. `uv run ruff format .` — auto-format. Safe; rewrites style only.
2. `uv run ruff check --fix .` — lint and auto-fix what's mechanically fixable
   (import sorting, simple modernizations). Read the remaining reports and fix
   them by hand.
3. `uv run pyrefly check` — type check. Fix every reported error.

Re-run after edits until all three are clean. The Stop hook and CI run
`ruff check` and `pyrefly check` *non-mutating* — so any formatting or fix you
leave unapplied will bounce the task back. Apply fixes yourself rather than
relying on the gate to catch them.

## ruff

The enabled rule sets (in `[tool.ruff.lint]` `select`) are `F` (pyflakes),
`E`/`W` (pycodestyle), `I` (import sorting), and `UP` (pyupgrade). `ruff format`
handles layout; `ruff check` enforces the rules. Most `I` and `UP` findings
auto-fix with `--fix`; logic findings (`F`) usually need a real edit.

To broaden coverage, add rule codes to `select` (e.g. `B` for flake8-bugbear).
Keep the pre-commit `rev` and the `pyproject.toml` `ruff>=` floor in step when
you bump ruff, so commit-time and CI use the same behavior.

## pyrefly (strict preset)

`strict` is the headline choice: on top of the default checks it flags implicit
`Any` and discourages untyped code, so new projects start with good typing
hygiene. The preset ladder, weakest to strongest, is
`off` < `basic` < `legacy` < `default` < `strict`.

Each error prints an error kind in brackets, e.g.
`[implicit-any-parameter]`, `[bad-return]`, `[missing-attribute]`. The kind
tells you what's wrong and, when you genuinely can't fix it, exactly what to
suppress. Always prefer a real fix — adding the missing annotation or correcting
the type — over silencing.

**Tests.** `tests/` is type-checked, but a `[[tool.pyrefly.sub-config]]` block
relaxes `implicit-any` there, so unannotated pytest fixture params
(`def test_x(tmp_path):`) don't force annotations. Imports, undefined names, and
type mismatches are still checked in tests. Annotate fixture params anyway when
it's cheap — the cheat-sheet (`tmp_path: Path`,
`monkeypatch: pytest.MonkeyPatch`, etc.) is in the guide.

**Semver caveat.** pyrefly does *not* follow strict semver — any release, even a
patch, may surface new errors. The version is pinned via `uv.lock`; upgrade
deliberately and re-run the checks, rather than auto-merging dependency bumps.

## Adopting pyrefly in an existing codebase

When pointing pyrefly at a project that has never been type-checked (or is
migrating from mypy/pyright), a clean `strict` run is unrealistic on day one.
Stage the adoption:

- `pyrefly init` — migrate an existing mypy/pyright config into `[tool.pyrefly]`.
- `uv run pyrefly check --baseline=pyrefly-baseline.json` then
  `--update-baseline` (or the `baseline = "..."` config key) — record current
  errors as an accepted baseline so CI only fails on *new* ones. Burn the
  baseline down over time.
- `uv run pyrefly suppress` — insert inline `# pyrefly: ignore` comments for the
  current error set, to triage incrementally instead of all at once.
- `uv run pyrefly infer` — infer and write annotations for unannotated code,
  cutting the manual annotation load.
- `uv run pyrefly coverage report` — emit a JSON type-coverage report to track
  progress (note: the subcommand is `coverage report`, not `report`).

Reach for suppression and baselines only during migration. In steady state, the
goal is zero suppressions and a clean `strict` run.
