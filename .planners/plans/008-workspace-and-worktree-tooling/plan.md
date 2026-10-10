---
id: 8
slug: workspace-and-worktree-tooling
status: done
branch: feature/workspace-and-worktree-tooling
created: 2026-09-26T00:32:54-07:00
concluded: 2026-10-09T21:31:55-07:00
pr: https://github.com/gitronald/proj-template/pull/47
---

# Make the hook, pyrefly, and ruff config workspace- and worktree-safe

## Plan

Four divergences surfaced while upgrading a downstream repo that is a uv
workspace (an unbuilt root plus one member package with its own
`pyproject.toml`) and does its plan work in worktrees under `.worktrees/`.
Each is a general property of the template's own recommendations, not of that
repo, so the template should carry the fix. Two are template files, two are
config the install skill should apply and document. A fifth item (chunked
commits vs the whole-tree pyrefly hook) is a skill note only.

### 1. Stop hook: resolve the root from git, not the first `pyproject.toml`

`template/.claude/hooks/lint-typecheck.sh` walks up from the cwd to the nearest
`pyproject.toml`. In a uv workspace the member package has its own, so a
session whose cwd is inside the member lints only that subtree: `ruff check .`
and `ruff format --check .` resolve `.` against the cwd, and files outside it
(skill scripts under `.claude/`, root-level scripts) are never checked while
the hook still exits 0. CI, which runs from the repo root, then fails on what
the gate passed.

Prefer the git toplevel of the cwd, which is the worktree root inside a
worktree and the repo root otherwise, and keep the walk as the fallback for a
cwd outside any repo:

```bash
root=$(git rev-parse --show-toplevel 2>/dev/null || true)
if [ -z "$root" ] || [ ! -f "$root/pyproject.toml" ]; then
    root=$PWD
    while [ ! -f "$root/pyproject.toml" ] && [ "$root" != "/" ]; do
        root=$(dirname "$root")
    done
fi
[ -f "$root/pyproject.toml" ] || root=${CLAUDE_PROJECT_DIR:-$PWD}
```

Update the comment above it to say why (workspace members). Under the
"Diverging files" rule this is template-owned plumbing, so an upgrade replaces
the old hook silently; say so in the changelog.

### 2. pyrefly: disable the default exclude heuristics

pyrefly's default `project-excludes` heuristics skip any *hidden* path
component, matched against the absolute path. A worktree under `.worktrees/`
therefore has every file excluded: `pyrefly check` prints `No Python files
matched pattern` and exits 0, so the Stop hook and the pre-commit hook pass
without checking anything. The template recommends exactly that worktree
layout.

In `template/pyproject.toml`, set `disable-project-excludes-heuristics = true`
under `[tool.pyrefly]` and list the excludes the heuristics used to supply:

```toml
project-excludes = ["**/__pycache__", "**/.venv", "**/.git", ".worktrees/**"]
```

The worktree exclude must be config-relative (`.worktrees/**`); the
`**/.worktrees` spelling matches the worktree's own absolute path and
reproduces the blindness. Add a comment saying so. The install skill's
"pyrefly on legacy code" note gains a sentence: a `No Python files matched`
result inside a worktree is this, not an empty project.

### 3. ruff: exclude Markdown from the formatter

ruff 0.16 formats the Python fences inside Markdown files, so `ruff format`
rewrites READMEs, CHANGELOGs, guides, and plan files whose fences were written
as prose. In `template/pyproject.toml` add `extend-exclude = ["*.md"]` under
`[tool.ruff]` with a one-line comment. Repos that want fenced code formatted
can drop the line; the default keeps the formatter off prose.

### 4. Keep the pre-commit ruff rev and the locked ruff in step

`template/.pre-commit-config.yaml` pins `ruff-pre-commit` to a tag while the
dev group says `ruff>=0.15`; the pre-commit hook installs its own ruff at the
tag and `uv run ruff` (CI, the Stop hook) uses whatever the lock resolved, so
the two can disagree on a formatting rule and a commit that passes pre-commit
fails `ruff format --check` in CI. Two changes:

- Pin the dev group to the same minor as the hook (`ruff>=0.16,<0.17`) so a
  fresh scaffold resolves the same rule set, and bump both together on a
  template release.
- Add an install-skill note under "Verify, then enable the hook gate": after
  `uv sync`, compare `uv run ruff --version` with the `rev` in
  `.pre-commit-config.yaml` and move the rev to the locked version when they
  differ (Dependabot's `uv` ecosystem bumps the lock; nothing bumps the hook
  rev).

### 5. Skill note: chunked commits vs the whole-tree pyrefly hook

The pre-commit `pyrefly-check` hook runs the whole tree (`pass_filenames:
false`). pre-commit stashes unstaged changes before each commit, so while an
upgrade is landing annotations in chunks the hook sees a half-annotated tree
and fails every chunk, and a failed hook leaves the chunk's files staged so
the *next* commit swallows them. Add to the install skill's "Commit, PR, and
close the plan" section: commit intermediate chunks with `--no-verify`, gate
on `uv run pre-commit run --all-files` over the final tree, and never commit
after a failed hook without re-checking `git status`.

### Out of scope

- The hook order (`ruff-format` before `ruff --fix`) is the reverse of
  ruff-pre-commit's documented order; it costs at most one extra commit
  attempt and is left alone here.
- CI extras a downstream repo needs (system packages such as pandoc, dependency
  groups it must exclude) stay repo-specific; the skill already says existing
  workflows are repo features.

### Implementation order

1. Hook (item 1) with a test that runs it from a workspace member's directory
   and from a worktree in `tests/`, if the suite already exercises the payload;
   otherwise a documented manual probe in the PR.
2. `pyproject.toml` items 2, 3, and 4's pin.
3. Skill text for items 2, 4, and 5.
4. CHANGELOG `[Unreleased]` entry naming the hook replacement as a silent
   upgrade under the diverging-files rule.

## Log

- **2026-10-09T12:42:07-07:00** — Items 1, 3, 4, and 5 implemented; item 2 held.
  - Item 1: the Stop hook prefers `git rev-parse --show-toplevel` and keeps the walk-up as
    the fallback (`8254768`). `tests/proj-init.test.sh` now runs the scaffolded hook with a
    `uv` stub that records its directory, from a workspace member, from a worktree, and from
    a member outside any repo (`b26eb7d`, `32a464b`). A manual probe confirmed the new check
    is meaningful: the previous hook resolved to the member, the new one to the repo root.
    Suite: all checks passed; `shellcheck` clean.
  - Item 3: probed ruff 0.16.6 on a Markdown file with an unformatted Python fence; it
    reports "1 file would be reformatted", and `extend-exclude = ["*.md"]` silences it.
  - Item 4: dev pin `ruff>=0.16,<0.17` (`b667807`); install-skill note under "Verify, then
    enable the hook gate", plus the same rule in `docs/guides/pre-commit.md`, whose
    `autoupdate` instructions would otherwise leave the pin behind (`570a2b7`).
  - Item 5: install-skill note under "Commit, PR, and close the plan" (`570a2b7`).
  - Item 2 did **not** reproduce. pyrefly 1.0.0 and 1.3.2 both checked a file under
    `<repo>/.worktrees/wt/` with the template's current config, with a bare
    `project-includes = ["."]`, and with only `preset = "strict"`; running the template's
    own config from this repo's worktree also matched files. The `**/.worktrees` spelling
    did not blind it either. No change made to `[tool.pyrefly]` or the pyrefly skill note.
  - CHANGELOG `[Unreleased]` entry added, naming the hook replacement as a silent upgrade.

- **2026-10-09T12:59:13-07:00** — Item 2 shipped as a guard, on the user's answer to
  question 1 (`069d343`). `[tool.pyrefly]` sets `disable-project-excludes-heuristics = true`
  with `project-excludes = ["**/__pycache__", "**/.venv", "**/.git", ".worktrees/**"]`; the
  install skill's pyrefly note names the `No Python files matched` symptom. Probed on
  pyrefly 1.0.0 and 1.3.2: both accept the key; a main-checkout run reports only its own
  file (the nested `.worktrees/wt` file is excluded), and a run inside the worktree still
  checks its own file. CHANGELOG entry added. CI on PR #47 (before this commit) passed on
  Linux and macOS, plus shellcheck.

- **2026-10-09T21:32:42-07:00** — Close: review gate (`/code-review`, medium), fixes,
  checks.
  - Review follow-up: two finders (correctness; reuse and docs) gave six candidates; three
    verifiers left two. Posted to PR #47.
    - CONFIRMED, `template/pyproject.toml`: `disable-project-excludes-heuristics = true`
      dropped pyrefly's default skipping of other virtualenvs, hidden directories, and
      `node_modules`. Reproduced on pyrefly 1.3.2: 1 error under the old config, 5 under
      the new (`venv/`, `.tox/`, `.ruff_cache/`, `node_modules/`). The heuristics left on
      still checked a file inside `.worktrees/wt/`. Actioned on the user's choice: item 2
      reverted (`364f41b`), CHANGELOG entry and skill note removed.
    - PLAUSIBLE, Stop hook: preferring the git toplevel made a nested project that is not
      a workspace member lint from the repo root. Actioned on the user's choice: the hook
      walks to the nearest project and switches to the toplevel only when its
      `pyproject.toml` declares `[tool.uv.workspace]` (`68f157f`). The tests now build a
      workspace repo and a non-workspace repo of their own, so the scaffold (and the CI
      manifest compare) is untouched. A probe shows the original hook fails the workspace
      check and this PR's first version fails the non-member check.
    - Conscious no-ops: a stale `hook.log` in the test helper (REJECTED: the uv stub exits
      0, so a failed call never writes the log); `**/.git` redundancy and hook
      simplification (confidence 20-25, moot after the revert and the rewrite).
  - Checks: `tests/portability.test.sh` and `tests/proj-init.test.sh` pass, `shellcheck`
    clean on every tracked script.

## Handoff

Closed. All five items are resolved: 1, 3, 4, and 5 shipped; 2 was reverted.

Questions:

1. Item 2 did not reproduce; ship it as a guard or drop it? Answered 2026-10-09: ship it.
   Superseded the same day after the review showed the regression: reverted, by the user's
   choice.

Not verified: the downstream pyrefly blindness that motivated item 2. It did not reproduce
on pyrefly 1.0.0 or 1.3.2; a repo that hits it should record its pyrefly version and config.

## Retrospective

- The plan's items came from one downstream upgrade and were written as findings, not
  hypotheses. Item 2 was not, and a probe before implementing caught it; shipping it
  anyway "as a guard" put a real regression in the PR for a failure nobody could trigger.
- A config flag that turns off a tool's defaults needs a probe of what those defaults
  covered, not only of the case it targets. The review found the cost in one run.
- The first hook fix overcorrected: "prefer the toplevel" fixed workspaces and broke
  nested projects. Keying it on `[tool.uv.workspace]` names the actual condition.
- Behavioral tests that record where the hook ran (a uv stub logging `pwd -P`) were cheap
  and made each regression a failing check; build their fixtures outside the scaffold so
  the cross-platform manifest stays unchanged.
