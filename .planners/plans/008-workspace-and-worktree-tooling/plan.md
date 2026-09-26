---
id: 8
slug: workspace-and-worktree-tooling
status: draft
branch:
created: 2026-09-26T00:32:54-07:00
concluded:
pr:
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
