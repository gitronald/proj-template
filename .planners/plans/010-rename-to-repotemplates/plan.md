---
id: 10
slug: rename-to-repotemplates
status: implemented
branch: feature/010-rename-to-repotemplates
created: 2026-11-06T20:59:46-08:00
concluded:
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

## Handoff

State on 2026-11-06:

- **In this repo (PR #58):** done and pushed. Every reference is renamed, the
  stamp is `[tool.repotemplates]`, the install-template skill renames an old
  `[tool.proj-template]` table during an upgrade, the scaffold script, its test,
  and the test skill are renamed (question 2), and there is an `[Unreleased]`
  changelog entry. The shell suite and shellcheck passed (see Log).
- **GitHub:** renamed to `repotemplates`, and `origin` in the local clone points
  at the new URL. The old URL redirects. Never create a new `proj-template` repo
  under the same account, because that breaks the redirect.
- **Local clone directory:** still named `proj-template`. Rename it outside a
  session that runs inside it, run `git worktree repair` afterwards (this plan's
  worktree records the old path), and rename the workspace's registry row for
  the clone at the same time. Tooling that finds the clone by its directory name
  breaks until that tooling is updated.

Open questions:

1. PyPI claim: still open.
2. Rename the scaffold script and test skill: **answered 2026-11-06**, renamed in
   this plan.
3. How long the old-table fallback stays: still open. It belongs with the reader
   update, outside this repo.

Remaining order:

1. Review and merge PR #58, then cut the minor release with stanza (expected
   0.12.0; the README and the install-template skill name that version). Waits
   on the owner.
2. Rename the local clone directory and the registry row (above). Waits on the
   owner.
3. Update the stamp readers and the clone-name lookups in other repos, before the
   fleet's next template upgrade pass. Tracked outside this repo.
4. The fleet moves to the new table in that pass.
