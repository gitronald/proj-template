---
name: install-template
description: Scaffold a new repo from proj-template or upgrade an existing repo to the latest template standard (uv, ruff, pyrefly, pre-commit, Claude hooks, GitHub Actions, planners, stanza). Use whenever the user wants to create a new project from the template, "install the template", bring a repo "up to standard", sync a repo with proj-template, or retrofit the template's tooling onto an existing package, app, or site — even if they only name one piece of it (e.g. "add the lint hooks from the template").
---

# Install template

Two modes. Pick by whether the target path already exists as a repo:

- **New repo** — target doesn't exist: run the scaffold script.
- **Upgrade** — target is an existing repo: sync it to the template standard
  file by file, adapting to what the repo is.

The template source of truth is the `template/` directory of this repo
(proj-template). Always read the current contents of `template/` rather than
relying on this document for exact file contents — the template evolves and
this skill describes the *process*, not frozen payloads.

## Mode 1 — New repo

Run the scaffold script (it clones the template, replaces `PACKAGE`
placeholders, fetches a license, sets up git/uv/pre-commit/stanza):

```bash
scripts/proj-init.sh [--license <key>] [--deps dependabot|renovate] <path>
```

The basename of `<path>` becomes the package name. The script is interactive
about `--deps` when run on a TTY — pass `--deps dependabot` explicitly when
running it from a tool. If the user chose renovate, finish with the
`/install-renovatabot` skill after the repo exists on GitHub.

## Mode 2 — Upgrade an existing repo

### Preflight

1. Require a clean working tree in the target repo; stop and report if dirty.
2. Classify the repo — this drives the sync matrix below:
   - **package**: built and published (has `[build-system]`, a `project.scripts`
     entry, or an importable package dir destined for PyPI).
   - **app/site**: run in place, never published (Pelican/Flask sites, analysis
     repos, dashboards). Marker: no build backend, or files like
     `pelicanconf.py`, `app.py`, `tasks.py`.
3. Create a branch off `dev` (or the repo's default working branch):
   `feature/template-upgrade`.

### Sync matrix

Work through every file in `template/`, applying the action for the repo type.
"Merge" means bring the template's entries/sections in without removing
repo-specific content; "never" means leave the repo's file alone.

| Template path | package | app/site |
|---|---|---|
| `pyproject.toml` `[tool.ruff*]`, `[tool.pyrefly*]` sections | merge | merge |
| `pyproject.toml` dev group (`ruff`, `pyrefly`, `pre-commit`) | merge | merge |
| `pyproject.toml` dev group (`pytest`, `pytest-cov`), `[tool.pytest.ini_options]` | merge | only if `tests/` exists |
| `pyproject.toml` `[build-system]`, sdist `only-include`, `[project.urls]`, `[project.scripts]` | merge | skip |
| `.pre-commit-config.yaml` | sync hooks (keep extra local hooks) | sync hooks (keep extra local hooks) |
| `.python-version` | sync | sync unless repo pins older deliberately |
| `.gitignore` | merge entries | merge entries |
| `.claude/settings.json`, `.claude/hooks/lint-typecheck.sh` | copy (merge if settings exist) | copy (merge if settings exist) |
| `.claude/CLAUDE.md` | never overwrite an existing one | never overwrite an existing one |
| `.github/workflows/test.yml` | sync (full Python matrix) | adapt: single Python from `.python-version`; drop pytest step if no tests |
| `.github/workflows/publish.yml` | sync | skip |
| `.github/dependabot.yml` (or renovate pair) | ensure one automation exists; merge ecosystems | same |
| `.planners/` scaffold | create if missing | create if missing |
| `PACKAGE/`, `tests/`, `README.md`, `CHANGELOG.md` | never | never |

Notes:

- **`.claude/` is on-disk, untracked.** The template standard ignores
  `.claude/` in the target's `.gitignore`, so the payload lands on disk but is
  never committed in the target repo. Exception: if the target already tracks
  `.claude/` files (e.g. its own skills), keep tracking and commit the new
  payload as tracked files too — don't untrack the repo's existing skills.
- **`.gitignore` merge**: add any template entries the repo lacks (notably
  `.claude/`, `.worktrees/`, `.env` block with `!.env.example`); keep all
  repo-specific entries (build output dirs, caches, data).
- **pyrefly on legacy code**: keep the template's `strict` preset. Before
  fixing anything, summarize errors per file and per rule — the shape decides
  the strategy. A file with `missing-import` errors whose imports aren't
  project deps (e.g. a legacy `tasks.py` using `invoke`) can't be meaningfully
  checked: add it to `project-excludes` immediately, don't annotate it. For the
  rest, fix the cheap errors (most are mechanical parameter annotations), then
  scope what remains out with `project-excludes` or
  `[[tool.pyrefly.sub-config]]` relaxations on the legacy paths (e.g. vendored
  themes, generated config) rather than weakening the global preset — new code
  stays strict.
- **Existing CI workflows** (deploy, docs, etc.) are repo features — leave them.
- **Action pinning**: workflows ship with actions pinned to specific version
  tags (e.g. `actions/checkout@v6.0.3`) because Dependabot — the default
  updater — doesn't keep SHA pins current. Don't "harden" them to SHA digests
  during an upgrade; that conversion belongs to Renovate enrollment
  (`/install-renovatabot`), whose `helpers:pinGitHubActionDigests` preset PRs it
  automatically.

### Verify, then enable the hook gate

Install and run everything; the upgrade isn't done until all of these pass in
the target repo:

```bash
uv sync --all-groups
uv run ruff check . && uv run ruff format --check .
uv run pyrefly check
uv run pre-commit install && uv run pre-commit run --all-files
uv run pytest   # only if the repo has tests
```

Run the autofixers before reading lint output: `uv run ruff format .` then
`uv run ruff check --fix .` clear most errors on their own, so only study what
survives them (typically long string literals and idioms needing a targeted
`# noqa`). Fix the rest at the source (annotate or exclude for pyrefly) — do
not commit with red checks. If the lint/format/annotation fixes touch a script
that generates output (site pages, reports, build artifacts), prove the
behavior is unchanged: copy the pre-upgrade version from git to a sibling path
in the *same directory* (so its `__file__`-relative paths still resolve — a
copy in `/tmp` silently reads the wrong inputs), run old and new against the
same explicit inputs into temp outputs, and diff for byte-identical results.
The
`.claude/settings.json` Stop hook runs ruff + pyrefly on every Claude session
stop, so a repo with failing checks would gate every future session; that is
why green checks are a hard requirement before this lands.

### Commit and report

Commit in logical chunks (e.g. tooling config, CI, gitignore), following the
repo's commit conventions. Then report what was synced, what was adapted for
the repo type, and what was deliberately skipped — and note that `.claude/`
changes are on-disk only.
