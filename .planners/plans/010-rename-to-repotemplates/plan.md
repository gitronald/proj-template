---
id: 10
slug: rename-to-repotemplates
status: done
branch: feature/010-rename-to-repotemplates
created: 2026-11-06T20:59:46-08:00
concluded: 2026-11-06T21:32:57-08:00
pr: https://github.com/gitronald/repotemplates/pull/58
---

# Rename the repo to repotemplates

## Plan

### Goal

Rename this repo from `proj-template` to `repotemplates`, on GitHub, in its own
files, and in the template payload it writes into generated repos, then carry the
rename to the repos that reference it. Plan 011 grows the repo from one template
to several, and the new name describes that: a set of repository templates, not
one project template.

### Name check (2026-11-06)

PyPI's JSON API, `curl -s -o /dev/null -w '%{http_code}' https://pypi.org/pypi/<name>/json`:

| Name | Result |
|---|---|
| `repotemplates` | 404, free |
| `repo-templates` | 404, free |
| `repotemplate` | 404, but see below |
| `repo-template` | 200, another author's project |
| `proj-template` | 200, another author's project |

`proj-template` on PyPI is a different project by another author, so this repo
could never publish under its current name. That is a second reason for the
rename.

`repotemplate` is not a real option even though it returns 404. Before PyPI creates
a project it removes `-`, `_`, and `.` from the name and maps look-alike characters,
and it refuses a name that then collides with an existing project. Without its
hyphen, `repo-template` becomes `repotemplate`, so that name is blocked.
`repotemplates` reduces to nothing that exists. Not verified by an upload; the
first real upload settles it.

GitHub: `gh repo view OWNER/repotemplates` and `OWNER/repotemplate` both fail to
resolve, so both names are free under the owner account.

### Decision: plural

Use `repotemplates`. The repo will hold several templates (plan 011), the singular
form is blocked on PyPI, and the plural keeps the GitHub, directory, PyPI, and
stamp names identical.

A 404 does not reserve the name. Only an upload does, and the repo is not a Python
package today (the root `pyproject.toml` is tooling only, with no `[project]`
table). See open question 1.

### What changes in this repo

- **GitHub**: `gh repo rename repotemplates`. GitHub redirects the old URL for
  clones, fetches, and web links, so nothing breaks right away. Never create a new
  repo named `proj-template` under the same account afterwards, because that
  removes the redirect.
- **Local clone**: rename the directory and run `git remote set-url origin` to the
  new URL. Any tooling that finds the clone by its directory name needs
  updating at the same time.
- **Docs and agent files**: `README.md` title and body, `.claude/CLAUDE.md`,
  `docs/guides/*`, and the `install-template`, `test-proj-init`, and
  `install-renovatabot` skills.
- **Scripts and tests**: `scripts/proj-init.sh` (usage text, `--source` default,
  messages), `tests/proj-init.test.sh`, and `tests/portability.test.sh`.
- **Template payload**: the guide URLs in `template/.github/dependabot.yml`,
  `renovate.json`, and `workflows/renovate.yml`, and the stamp table in
  `template/pyproject.toml`.
- **Changelog**: an `[Unreleased]` entry naming the rename and the stamp migration.
- **Left as written**: earlier plans and released changelog sections. They are a
  record of the repo under its old name.

Find every remaining reference with `git grep -n -e proj-template -e proj_template`
and sort out the historical ones by hand.

### The template stamp

Generated repos carry `[tool.proj-template] version = "X.Y.Z"` in
`pyproject.toml`. Tools outside this repo read that table to find out which
release a repo was built from. The rename moves it to `[tool.repotemplates]`:

1. Readers accept both tables, preferring `[tool.repotemplates]`. This ships
   first, in the repos that hold the readers, **before** any generated repo can
   carry the new table.
2. This repo's release writes `[tool.repotemplates]`. `install-template`'s upgrade
   mode replaces an existing `[tool.proj-template]` table with the new one,
   keeping its version until the upgrade's last step bumps it, as it does today.
3. Once no clone still carries the old table, readers drop it (open question 3).

### Downstream repos

The repos that reference this one are not named here. Find them by searching the
local clones (each clone's tracked files, with `git grep -lI -e proj-template -e
proj_template`), and keep the list of repos in the workspace's own tracking,
outside this repo.

A search on 2026-11-06 found tracked references in about 37 clones, of these
kinds:

| Kind | Action |
|---|---|
| `[tool.proj-template]` stamp in `pyproject.toml` | migrate during the next template upgrade (stamp step 2) |
| Guide URLs in `.github/dependabot.yml` and `renovate.json` comments | updated by the same upgrade; the redirect covers the gap |
| Tooling code that reads the stamp table, or finds this repo's clone by name | update first (stamp step 1), with tests |
| Agent skills and global rules that name the repo | update with the code |
| Released changelog lines and closed plan files | leave as written |

### Order

1. Readers in other repos accept both stamp tables, and are released.
2. On a branch here: rename every reference in this repo, write the new stamp, and
   add the upgrade-mode migration to `install-template`. Run the shell suite and
   `shellcheck`.
3. Rename the GitHub repo, the local directory, and the remote URL, and update
   any tooling that finds the clone by name, all at once.
4. Merge, and cut a minor release with stanza (the stamp table changes).
5. The fleet moves to the new stamp in its regular template upgrade pass.
6. Later: remove the old-table fallback from the readers.

### Open questions

1. Claim `repotemplates` on PyPI, and when? Only an upload reserves it. Upload a
   real package (plan 011 could add a small `uvx repotemplates init` CLI), not a
   placeholder, since PyPI can give unused names to someone else.
2. Rename `scripts/proj-init.sh` and the `test-proj-init` skill too
   (e.g. `scripts/init.sh` and `test-init`)? This fits with plan 011's
   `--template` flag, so it may land there instead.
3. How long does the old-table fallback stay: until the fleet has moved, or for
   a fixed number of releases?

## Log

- **2026-11-06T21:04:34-08:00** — Name confirmed by the owner: repotemplates (plural), as the Decision section proposes.
- **2026-11-06T21:12:52-08:00** — Activated.
  - Branch: `feature/010-rename-to-repotemplates`
  - Base: `dev` at `429f066`
  - Worktree: `.worktrees/010-rename-to-repotemplates`
  - PR: pending
- **2026-11-06T21:19:40-08:00** — PR opened: https://github.com/gitronald/proj-template/pull/58
- **2026-11-06T21:20:29-08:00** — Owner decisions on the order and open question 2.
    - Order: this repo's rename lands first. The update to the stamp readers in other repos follows it, tracked in the workspace's own planning outside this repo, and has to ship before the fleet's next template upgrade pass. That pass is the first time a generated repo carries `[tool.repotemplates]`, because the install-template migration renames the table only during an upgrade.
    - The GitHub rename (order step 3) happens in this session, before the merge. The redirect keeps the old URL working in the meantime.
    - Question 2 answered: rename now. `scripts/proj-init.sh` is now `scripts/init.sh`, `tests/proj-init.test.sh` is `tests/init.test.sh`, and the `test-proj-init` skill is `test-init`. The README alias is `repo-init`.
    - Checks on caa3011 and 12b89ef: `tests/portability.test.sh` passed, `tests/init.test.sh` passed (including `[tool.repotemplates] stamped with VERSION 0.11.8a0`), and shellcheck over every tracked `.sh` was clean.
- **2026-11-06T21:24:10-08:00** — PR opened: https://github.com/gitronald/repotemplates/pull/58
- **2026-11-06T21:24:24-08:00** — Implemented: 6 commits ahead of `dev`.
- **2026-11-06T21:30:09-08:00** — Local clone directory renamed to repotemplates by the owner. Repaired the plan worktree's link with git worktree repair, rebuilt the root and worktree venvs with uv venv --clear and uv sync (both held the old path in their shebangs), and reinstalled the pre-commit and post-merge hooks from the main checkout, since their INSTALL_PYTHON pointed at the old venv and they had stopped running. planners install --check reports both hooks active.
- **2026-11-06T21:33:22-08:00** — Review gate run at medium on PR #58; CI green on shellcheck and the Linux and macOS test jobs.
  - Review follow-up: 13 candidates from two finders. Actioned: one TEMPLATE_CLONE variable for the clone path in scripts/init.sh, a reworded clone-check comment, and a realigned comment column in the test-init skill; the existing init test covers the clone path through the VERSION stamp check. Conscious no-ops: 0.12.0 named before release (a minor bump from 0.11.x), the rename guidance repeated for different readers in CHANGELOG, README, and the skill, the legacy proj-init trigger phrases kept in the test-init description, and the init.sh --version prefix change (no consumer found). Portability test, init test, and shellcheck pass after the fix.

## Handoff

State on 2026-11-06:

- **In this repo (PR #58):** reviewed and merged into `dev` when this plan closed.
  Every reference is renamed, the stamp is `[tool.repotemplates]`, the
  install-template skill renames an old `[tool.proj-template]` table during an
  upgrade, the scaffold script, its test, and the test skill are renamed
  (question 2), and there is an `[Unreleased]` changelog entry. The shell suite
  and shellcheck passed after the review fixes (see Log).
- **GitHub:** renamed to `repotemplates`, and `origin` in the local clone points
  at the new URL. The old URL redirects. Never create a new `proj-template` repo
  under the same account, because that breaks the redirect.
- **Local clone directory:** renamed to `repotemplates`. The worktree link,
  both venvs, and the git hooks are repaired (see Log). Not done here: the
  workspace's registry row for the clone, which lives outside this repo. Tooling
  that finds the clone by its directory name breaks until that row and that
  tooling are updated.

Open questions:

1. PyPI claim: **handed to plan 011** (2026-11-06), which may add the small
   `uvx repotemplates init` CLI whose upload would claim the name. Not verified:
   that PyPI accepts `repotemplates`; only the first upload settles it.
2. Rename the scaffold script and test skill: **answered 2026-11-06**, renamed in
   this plan.
3. How long the old-table fallback stays: **handed to the stamp-reader update**
   (2026-11-06), tracked in the workspace's planning outside this repo.

Remaining order:

1. Cut the minor release with stanza (expected 0.12.0; the README and the
   install-template skill name that version). Waits on the owner.
2. Rename the workspace's registry row for the clone (the directory is
   renamed). Waits on the owner, outside this repo.
3. Update the stamp readers and the clone-name lookups in other repos, before the
   fleet's next template upgrade pass. Tracked outside this repo.
4. The fleet moves to the new table in that pass.

## Retrospective

- The rename went as planned in this repo, with one change of scope: open question 2
  was answered "now", so the scaffold script, its test, and the test skill were
  renamed here instead of waiting for plan 011.
- The order moved: the original plan had the stamp readers ship first, but the owner
  put this repo first, because a generated repo only carries the new table after an
  upgrade pass. That keeps the reader update off the critical path for this merge.
- Renaming the local clone directory broke more than the remote URL: the worktree
  link, both venvs (their shebangs held the old path), and the git hooks (their
  `INSTALL_PYTHON` pointed at the old venv, so they stopped running without a
  warning). A rename checklist should include all four.
- A search-and-replace rename leaves the old name's grammar behind ("a
  repotemplates this script can fill in"), and a path repeated five times got five
  edits instead of one variable. The review caught both, and it is worth reading
  the replaced lines as prose, not only grepping for leftovers.
