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

Run the scaffold script (it clones the template, replaces the `PROJECT__NAME` and
`MODULE__NAME` placeholders, fetches a license, sets up git/uv/pre-commit/stanza):

```bash
scripts/proj-init.sh [--license <key>] [--source <repo>] [--deps dependabot|renovate] <path>
```

`--source` clones a local proj-template checkout or a fork instead of the GitHub repo
(committed changes only).

The basename of `<path>` becomes the project name (dashes map to underscores
in the Python module name). The script is interactive
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
3. Plan the upgrade in the target repo's own plan system, the same way
   `/planners add` + `/planners implement` would:
   - If `.planners/` is missing, scaffold it first — it's part of the upgrade
     anyway (see the sync matrix).
   - Create the plan (`planners add template-upgrade`, next free `NNN`) and
     write the spec into it: the repo classification, the sync decisions per
     matrix row, and what will be deliberately skipped. Keep it free of
     machine-specific paths.
   - Open a worktree instead of switching the main checkout: branch
     `feature/template-upgrade` off `dev` (or the repo's default working
     branch) at `.worktrees/template-upgrade`. Check the target's
     `.gitignore` first and add `.worktrees/` if it isn't ignored.
     Do all tracked upgrade work inside the worktree. The exception is
     gitignored payload: when the target ignores `.claude/`, the worktree
     has no copy of `.claude/CLAUDE.md`, `settings.json`, `settings.local.json`,
     or `hooks/`, and
     anything written there vanishes when the worktree is removed. Apply
     the `.claude/*` rows in the main checkout instead, and note in the
     PR that those files changed on disk outside the branch.
   - Set the plan `status: active` and fill `branch`, and commit the plan on
     the feature branch so it rides in the PR.

### Sync matrix

Work through every file in `template/`, applying the action for the repo type.
"Merge" means bring the template's entries/sections in without removing
repo-specific content; "never" means leave the repo's file alone. When the
target already has a managed file and its content diverges from `template/`,
the row's action is not automatic — see "Diverging files are a question, not an
overwrite" below.

| Template path | package | app/site |
|---|---|---|
| `pyproject.toml` `[tool.ruff*]`, `[tool.pyrefly*]` sections | merge | merge |
| `pyproject.toml` dev group (`ruff`, `pyrefly`, `pre-commit`) | merge | merge |
| `pyproject.toml` dev group (`pytest`, `pytest-cov`), `[tool.pytest.ini_options]` (`addopts` uses bare `--cov`; drop a repo's `--cov=<pkg>` since `run.source` names it), `[tool.coverage.*]` (set `run.source` to the repo's package) | merge | only if `tests/` exists |
| `pyproject.toml` `[build-system]`, sdist `only-include`, `[project.urls]`, `[project.scripts]` | merge | skip |
| `pyproject.toml` `[tool.proj-template]` `version` | stamp the release being applied (see note) | same |
| `.pre-commit-config.yaml` | sync hooks (keep extra local hooks) | sync hooks (keep extra local hooks) |
| `.python-version` | sync | sync unless repo pins older deliberately |
| `.gitignore` | merge entries | merge entries |
| `.claude/settings.json`, `.claude/settings.local.json`, `.claude/hooks/lint-typecheck.sh` | copy when absent; when either settings file exists, **ask** — never copy over it (see note); apply in the main checkout when `.claude/` is gitignored (see preflight) | same |
| `.claude/CLAUDE.md` | relocate if in an old spot; never overwrite its content, except the `## Development` tooling bullets (see note) | same |
| `.github/workflows/test.yml` | sync (full Python matrix, `UV_PYTHON` env pin **and** `--python` on `uv sync` — see note, SHA-pinned actions) | adapt: single Python from `.python-version`; drop pytest step if no tests; SHA-pinned actions |
| `.github/workflows/publish.yml` | sync | skip |
| `.github/dependabot.yml` (or renovate pair) | ensure one automation exists; reconcile each ecosystem (groups, cooldown, `target-branch` — see note); set repo alert toggles (see note) | same |
| `.planners/` scaffold | create if missing | create if missing |
| `MODULE__NAME/`, `tests/`, `README.md`, `CHANGELOG.md` | never | never |

Notes:

- **Placeholders are never copied into a target.** `template/` carries
  `PROJECT__NAME` and `MODULE__NAME` wherever the scaffold substitutes the repo's
  own names — notably `pyproject.toml`'s `name`, `[project.urls]`,
  `[project.scripts]`, sdist `only-include`, and `[tool.coverage.run] source`.
  When a merge row brings in such a line, resolve the placeholder to the target's
  project name or package directory, and when diffing, treat a placeholder
  against the target's real name as a match, not a divergence. Repos scaffolded
  before 0.9.3 used the bare spellings `PROJECT` and `MODULE`; the same rule
  applies — a bare or double-underscored placeholder left in a target is always
  a bug, never a customization.

- **Diverging files are a question, not an overwrite.** Read this before
  applying any row. For every `sync`/`copy`/`merge` row, diff the target's
  existing file against `template/` first and sort the result:
  - **Absent, or identical** — apply the row silently; there is nothing to
    decide.
  - **Diverges, but the repo's copy holds nothing the template lacks** — the
    repo is simply carrying an older template revision. Replace it and say so
    in the report; no question, since nothing is lost. (Example: a repo
    upgraded before the Stop hook was made cwd-independent still has
    `"command": ".claude/hooks/lint-typecheck.sh"` in `.claude/settings.json`
    — stale template content with no repo value.)
  - **Diverges and the repo's copy holds content the template would drop or
    change** — a customized value, an extra entry, a different command or
    timeout — **ask before touching it.** Never assume the template wins: the
    repo may have diverged deliberately.

  Gather every file in this last class across the whole matrix *before* asking,
  then put them to the user in one batched `AskUserQuestion` round — do not
  interrupt once per file. Offer per file (or per tightly-related group, since
  a round holds at most four questions): **replace** with the template version,
  **merge** the template's change while keeping the repo's customization, or
  **keep** the repo's file as-is. Show the specific conflicting lines in the
  question so the choice is informed, and record each answer in the plan's Log
  with the reason, so the next upgrade doesn't re-litigate it.
- **The `[tool.proj-template]` stamp is exempt from the question above, and is
  written last.** It records which template release the repo carries, so it is
  never a merge and never a customization to preserve: overwrite whatever
  version is there, and add the table (after `[project.scripts]`) when a repo
  predates it. Write it only *after* the rest of the matrix has been applied and
  any batched questions answered, and only if the upgrade actually landed in
  full — if the user chose **keep** on rows that leave the repo behind the
  template, stamp the older release the repo still matches, or leave the stamp
  untouched and say so in the report. A stamp that overstates is worse than an
  absent one, since it makes the next upgrade skip the repo. The template ships
  the literal `TEMPLATE_VERSION` placeholder there (`proj-init.sh` substitutes
  it at scaffold time), so never copy that string into a target — resolve it to
  the release being applied, and treat a `TEMPLATE_VERSION` or `unknown` value
  found in a repo as "never stamped".
- **Claude settings are always a question, never a silent copy.** The
  `.claude/settings.json` / `.claude/settings.local.json` row is exempt from the
  "diverges but holds nothing the template lacks — replace silently" path above.
  `settings.local.json` is where Claude Code records the permission grants a user
  accepts in that repo, so a target's copy is *expected* to diverge and to grow
  with use; replacing it silently revokes grants the user chose, and the loss is
  invisible until a familiar command starts prompting again. Whenever either file
  differs from the template, put it in the ask-first class and fold it into the
  same batched round as everything else.

  State what adopting the template's version *would* change, per file, as three
  explicit lists — the question is uninformative without them:
  - **added** — entries the template has and the repo lacks. This is the actual
    upgrade; it is the part that is normally safe to take.
  - **removed** — entries the repo has and the template lacks. These are the
    repo's own accumulated or deliberate grants, so default to keeping them and
    say so; only a straight replace drops them.
  - **moved between lists** — an entry present in both files but under a
    different key. Name each one with its direction, because either direction
    changes what runs without a prompt: `ask`/`deny` -> `allow` broadens (the
    template allows `Bash(git push:*)`, which a repo may have deliberately kept
    on `ask`), and `allow` -> `ask`/`deny` tightens, which can stall a workflow
    the repo depends on. A move never rides along with the additions — it needs
    its own yes.

  Offer **merge** (take the additions, keep the repo's extras, apply only the
  moves the user accepts) as the default, with **replace** and **keep** as the
  alternatives. Hook definitions in `settings.json` are not part of this: a
  changed `command` or `timeout` there is template-owned plumbing and still
  replaces silently under the general rule — only a hook the repo added or
  edited itself is a question.
- **Relocate misplaced files; never duplicate.** The template moves files
  between versions, so before applying a row check whether the target already
  has that file in an *old/wrong* location (e.g. `CLAUDE.md` at the repo root
  when the standard now keeps it at `.claude/CLAUDE.md`). When it does — and it
  is genuinely the file this row manages, not a coincidental same-named file
  (confirm by content and role, not just basename) — `git mv` it to the
  canonical path first, then apply the row's normal action there. Moving beats
  leaving a stray copy or creating a second one. That is what "never overwrite"
  on the `.claude/CLAUDE.md` row means: preserve the existing content, but still
  move it into place when it is sitting in the old spot.
  The one content exception is the `## Development` section: its Install,
  Tests, Linting, Type checking, and CI bullets describe template-owned
  tooling, so refresh each of those bullets to the template's current wording
  when the repo's copy is stale (e.g. a bare `uv run pytest` line that does
  not mention the coverage gate). Match bullets by their leading label, keep
  any repo-specific bullets and text outside that section untouched, and skip
  a bullet the repo has clearly customized (a different command, extra flags).
- **Tracking `.claude/` is a per-repo decision.** The template default ignores
  `.claude/` in the target's `.gitignore`, so the payload lands on disk but is
  never committed. A repo may instead choose to track part of it (commonly
  `.claude/CLAUDE.md`, or its own skills). To keep one file tracked while
  ignoring the rest, ignore the *contents* and re-include the file — `.claude/*`
  then `!.claude/CLAUDE.md` — because a `!`-negation cannot re-include a file
  inside a wholly-ignored directory (`.claude/`). Whichever way a repo already
  leans, follow it: don't untrack files it commits, and don't start committing
  machine-local ones. `.claude/settings.local.json` is machine-local in *every*
  target repo — it carries the permission allow/deny/ask lists, so it stays
  untracked there no matter what else the repo commits. proj-template itself is
  the one exception: it tracks its copy, since that is the payload targets are
  upgraded from.
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
- **Action pinning**: workflows ship with actions pinned to commit SHAs with a
  `# vX.Y.Z` comment (e.g. `actions/checkout@3d3c42e…  # v7.0.1`), so a
  retagged or repointed release can't change what runs. Dependabot keeps these
  current under the default setup — it bumps the SHA and the version comment
  together — so SHA pins are safe with either updater. On upgrade, sync each
  pin to the template's SHA and comment. If a repo still has bare version tags,
  convert them: resolve each tag with
  `gh api repos/<owner>/<repo>/git/ref/tags/<tag>` (an annotated tag returns
  `object.type: tag`; dereference it via `git/tags/<sha>` to reach the commit)
  and keep the `# vX.Y.Z` comment — it is what makes the pin readable and what
  Dependabot updates alongside the SHA.
- **Dependabot repo settings — alerts on, security updates off.** Separate from
  `dependabot.yml` (which schedules *version* updates), set the GitHub repo's two
  security toggles deliberately: turn Dependabot **alerts** on
  (`gh api -X PUT repos/<owner>/<repo>/vulnerability-alerts`) and leave Dependabot
  **security updates** off (never enable `automated-security-fixes`). The
  scheduled grouped version-update PRs (with `cooldown`) plus the release-time
  vulnerability audit are the chosen update path, so security-update PRs would
  only duplicate them. Alerts stay on purely as a warning layer: they open no
  PRs, fire immediately on a new advisory (not gated by the schedule or
  `cooldown`), and auto-clear when the fix reaches the default branch. This
  mirrors the Renovate path, where `/install-renovatabot` already keeps alerts on
  and security-update PRs off. Verify with
  `gh api repos/<owner>/<repo>/vulnerability-alerts` (204 on / 404 off) and
  `gh api repos/<owner>/<repo>/automated-security-fixes` (`{"enabled":false}`).
- **Reconcile inner config, not just file presence.** A "sync"/"merge" row is
  satisfied only when the file's *contents* match the current `template/`, not
  when the file merely exists with the right top-level shape. Two traps seen in
  practice: a `test.yml` whose multi-version `python-version` matrix lacks the
  job-level `env: UV_PYTHON: ${{ matrix.python-version }}` — without it every
  cell silently re-resolves to `.python-version` and tests the *same*
  interpreter, so the matrix is a no-op; and a `dependabot.yml` that already
  lists both ecosystems but is missing the current `groups`/`cooldown` blocks.
  Diff each managed file against `template/` and carry stale inner config
  forward, don't stop at "the file is there." That diff is also what feeds the
  divergence triage in the first note — run it once and use it for both.
- **Don't "simplify" the redundant `--python` on `uv sync`.** `test.yml` passes
  `--python ${{ matrix.python-version }}` *and* sets `UV_PYTHON`; the env var
  alone is sufficient, so the flag reads like something to delete. It stays:
  the sync step fixes the interpreter the rest of the job inherits, so spelling
  it out there is what keeps a copied-out sync line — or an edit that drops the
  `env` block — from quietly reintroducing the no-op-matrix trap above. Carry
  it forward on a sync; never drop it as cleanup.
- **`target-branch: dev` — reconcile it, but check the branch exists first.**
  The template's `dependabot.yml` sets `target-branch: dev` on both ecosystems so
  update PRs open against the active branch and resolve manifests against the
  tree they will merge into. A repo upgraded from an older template revision will
  not have the key; add it per ecosystem — but only once the repo actually has a
  `dev` branch (`git rev-parse --verify origin/dev`). A scaffolded repo always
  does, since `proj-init.sh` creates and pushes `dev`; an older or non-template
  repo may not, and pointing Dependabot at a missing branch stops its updates.
  Two follow-ons: `dependabot.yml` is read from the **default** branch, so this
  edit is inert until it reaches `main`; and with `target-branch` set, that
  ecosystem's options no longer apply to *security* updates — moot under the
  alerts-on / security-updates-off setting above.

### Verify, then enable the hook gate

Install and run everything; the upgrade isn't done until all of these pass in
the target repo:

```bash
uv sync --all-groups
uv run ruff check . && uv run ruff format --check .
uv run pyrefly check
uv run pre-commit install && uv run pre-commit run --all-files
uv run pytest   # only if the repo has tests; runs with coverage via addopts
```

Coverage floor on an existing repo: merging `[tool.coverage.*]` brings in
`fail_under = 50`, which can fail `pytest` in a repo whose tests never reached
that. Do not drop the section or the `addopts` flag. Set `fail_under` to the
repo's current total (round down to a whole number) so the gate holds the line
from here, and say so in the report so the owner can raise it later. Set
`run.source` to the actual package directory; for an app or site with no
package, point it at the directory that holds the tested modules.

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

### Commit, PR, and close the plan

Commit in logical chunks (e.g. tooling config, CI, gitignore, code fixes),
following the repo's commit conventions, and append Log entries to the plan as
decisions land (what was adapted, what was excluded and why). Then:

1. Push the branch (`git push -u origin feature/template-upgrade`) and open a
   PR into `dev` summarizing synced/adapted/skipped per the sync matrix.
2. Close the plan the way `/planners close` does: on merge, set
   `status: done`, fill `concluded` from the merge commit timestamp and `pr`
   with the full PR URL, regenerate the index (`planners index .`), and remove
   the worktree (after removing, check `.git/hooks/pre-commit` for an embedded
   worktree venv path and re-install hooks from the main checkout if found).
   If the user wants to review before merging, stop after opening the PR and
   leave the plan `active`.

Report what was synced, what was adapted for the repo type, and what was
deliberately skipped — and note when `.claude/` changes are on-disk only.
