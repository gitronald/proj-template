# repotemplates

Python project template with uv, ruff, pyrefly, pytest, pre-commit, GitHub Actions CI, and stanza release automation.

## Prerequisites

The scaffold script needs these on your `PATH`, and stops before creating
anything if one is missing:

- [uv](https://docs.astral.sh/uv/) — installs Python and the project's dependencies
- [gh](https://cli.github.com/), authenticated (`gh auth login`) — fetches the license and your author name
- [stanza](https://github.com/gitronald/stanza) — creates the GitHub repo and drives releases
- `git` and `rsync`

[planners](https://github.com/gitronald/planners) is installed for you as a uv
tool if it is missing. Everything else a scaffolded project uses — ruff, pyrefly,
pytest, and pre-commit — comes from its own dev dependency group.

## Quick Start

Download and run the scaffold script to create a new project:

```bash
curl -s https://raw.githubusercontent.com/gitronald/repotemplates/main/scripts/init.sh | bash -s <path>
```

Or add an alias to your `.bashrc` or `.zshrc`:

```bash
alias repo-init='curl -s https://raw.githubusercontent.com/gitronald/repotemplates/main/scripts/init.sh | bash -s'
```

Then create a new project:

```bash
repo-init ~/repos/myproject
repo-init --license apache-2.0 ~/repos/myproject
repo-init --source ~/repos/repotemplates ~/repos/myproject   # scaffold from a local checkout or fork
```

With the `repotemplates` tool installed (see below), `repotemplates init` runs
the same script on the template that release ships, with no clone:

```bash
repotemplates init ~/repos/myproject
repotemplates init --license apache-2.0 --deps renovate ~/repos/myproject
```

`--source` still clones, so it scaffolds the source's committed tree: unpushed
commits are picked up, uncommitted edits are not. Without `--branch`, a local
checkout is cloned at whatever branch it has checked out; the script prints the
commit it used.

The script targets bash 3.2+, so it runs on stock macOS as well as Linux.

## What it does

1. Copies the template (the curl script clones it; `repotemplates init` uses the copy its release ships) and replaces placeholders: `PROJECT__NAME` becomes your project name, and `MODULE__NAME` becomes its Python module name (dashes become underscores)
2. Stamps the template release it used into `[tool.repotemplates]` in the new repo's `pyproject.toml`, so you can later tell which template version a repo carries (see [Template version stamp](#template-version-stamp))
3. Fetches a LICENSE file from GitHub's API (default: MIT)
4. Initializes a git repo on a `dev` branch
5. Installs dependencies with `uv sync`
6. Sets up pre-commit hooks and stanza
7. Makes the initial commit

## Template version stamp

Every scaffolded repo records the template release it came from:

```toml
[tool.repotemplates]
version = "0.9.0"   # whichever release scaffolded it, not a version to match
```

The version is read from the *cloned* template, so `--branch dev` records the
prerelease actually applied rather than whatever a local checkout happens to be
on. The `install-template` skill re-stamps it on upgrade — and deliberately does
not stamp a newer release when an upgrade only partly lands, since a stamp that
overstates would make the next upgrade skip the repo.

The table is inert to anyone installing your package: build backends translate
only `[project]`, so it never reaches the wheel or the PyPI metadata. It does
appear in the sdist, which carries `pyproject.toml` unconditionally.

Before the rename to `repotemplates` (0.12.0), the table was
`[tool.proj-template]`, with the same `version` key. A repo not yet upgraded past
that release still carries the old table, and the next `install-template` upgrade
renames it. Tools that read the stamp should accept both, preferring
`[tool.repotemplates]`.

To audit drift across repos, use `repotemplates check` (below).

## Checking a repo against the template

`repotemplates check` compares a repo with the template. It is read-only:
it never edits a repo (`repotemplates upgrade`, below, is the command that writes).

```bash
uv tool install repotemplates            # or run it once: uvx repotemplates check
repotemplates check                      # the repo in the current directory
repotemplates check path/to/repo --json  # one JSON object, for scripts
repotemplates check --repos-dir ~/repos  # every stamped clone, as one table
repotemplates init path/to/new-repo      # scaffold from this release's template
repotemplates version
```

For each repo it reports:

- **The stamp**: `latest`, `behind` or `ahead` of the newest release the tool
  knows, `alpha`, `unknown`, or `missing`. Both `[tool.repotemplates]` and the
  older `[tool.proj-template]` are read. A table with no `version` yet (written
  to hold `omit` or `keep` before the first stamp) reads `missing`, and its
  lists still count.
- **Each template-owned file**: `current` (matches the template this release
  ships), `matches vX.Y.Z` (an earlier release), `one-off` (matches no release),
  `kept vX.Y.Z` or `kept-behind vX.Y.Z` (a customization the repo keeps, below),
  `missing`, `omitted` (left out by design, below), or `retired` (a file the
  template no longer ships, still present). Each class has its own rule:
  - Claude hook scripts (`.claude/hooks/*.sh`), `.github/dependabot.yml`, and
    `.github/renovate.json`: exact content.
  - The `hooks` block of `.claude/settings.json`: normalized JSON, other keys
    ignored.
  - Pinned files (`.pre-commit-config.yaml` and the `test`, `publish`, and
    `renovate` workflows): compared with `rev:` values, action refs and their
    version comments, and the `python-version` matrix list masked. The pins get
    their own verdict: `same`, `ahead`, `behind`, `mixed`, or `differs`. A pin
    newer than the template's is `ahead`, which is not drift.
  - `.gitignore` and `.gitattributes`: every template rule must hold, which git
    answers for a probe path (`git check-ignore`, `git check-attr`), so spelling
    and local additions do not count. A rule is `partial` when it does not hold,
    and waived when the repo tracks a path the rule would ignore (a repo that
    tracks `.claude/settings.json` leaves out `.claude/` on purpose).
- **Files left out by design**: a repo on Dependabot has no Renovate files, and
  the reverse, so those read `omitted`. Any other file the repo leaves out on
  purpose is listed in the stamp table, which `check` cannot otherwise tell from
  a file lost by accident:

  ```toml
  [tool.repotemplates]
  version = "0.13.0"
  omit = [".github/workflows/publish.yml"]   # this repo does not publish
  ```
- **Files kept in the repo's own form**: a template file the repo customizes on
  purpose (a Stop hook with an extra step, a workflow with an added job) is
  recorded in the stamp table's `keep`, with the release it was last reviewed
  against. Such a file that matches no release reads `kept` while the
  template's copy is unchanged since that release, and counts as current. Once
  a later release changes the template's copy (pins aside), it reads
  `kept-behind` and is drift again until someone reviews the change and moves
  the release forward. Pins in a kept file are still compared.

  ```toml
  [tool.repotemplates]
  version = "0.15.0"
  keep = {".github/workflows/test.yml" = "0.15.0"}   # adds a docs job
  ```
- **Files a worktree ignores**: in a linked worktree (`git worktree add`), a
  template file the repo gitignores, such as `.claude/` in the template's own
  `.gitignore`, is not checked out. `check` reads it from the main worktree
  instead, and its row names where it was read; `upgrade` leaves it for that
  checkout.
- **The ruff rev against the lock**: the `ruff-pre-commit` rev in
  `.pre-commit-config.yaml` always equals the ruff in `uv.lock`, since the
  commit hook runs the one and CI the other. The pair gets a row of its own:
  `same`, `differs` (drift, even when every pin is current), or `unlocked` (no
  ruff in `uv.lock`). The template's rev is a floor: a lock newer than it leads
  the rev, and a lock older than it moves up to it.
- **Git state of the Claude settings files**: tracked, ignored, untracked, or
  absent. An ignored file never reaches a fresh clone or a cloud session; the
  template ignores `.claude/` by default, so this is information, not drift.

It exits 0 when the stamp is the latest and every file is current or omitted
with no pin behind, 1 when
anything differs or `--repos-dir` finds no repo to check, and 2 on a usage
error. `--markdown` prints Markdown tables.
With `--repos-dir`, `--json` prints an array, and `*-archive` repos and repos
with no stamp are skipped unless `--include-archived` or `--all` is given.

The tool carries the template and a manifest of every release's files, so it
needs no clone and no network.

## Upgrading a repo

`repotemplates upgrade` applies the mechanical part of an upgrade, and writes
only what `check` shows holds nothing of the repo's own:

```bash
repotemplates upgrade path/to/repo --dry-run   # what it would write and skip
repotemplates upgrade path/to/repo
```

- A file that equals an earlier release's copy takes this release's. A pinned
  file keeps the repo's newer pins and its Python matrix list, and
  `.claude/settings.json` has only its `hooks` block replaced.
- A pinned file whose pins are behind the template's has them raised.
- The `ruff-pre-commit` rev moves to the locked ruff, or to the template's rev
  when the lock is older (within the repo's `ruff` range in `pyproject.toml`),
  and ruff is relocked to exactly that version with
  `uv lock --upgrade-package ruff==<version>`. When uv cannot run, the row names
  that command and the stamp waits.
- A file `keep` records is left as it is.
- Anything else (a customized file, a kept one whose template copy has changed,
  a missing one, an ignore file lacking rules, a file read from the main
  worktree) is left, with the reason, for the `install-template` skill.
- The stamp moves to this release only when every file then reads current or
  omitted, so it never overstates what the repo carries. `--no-stamp` leaves it
  alone, for an upgrade with more to do than the files `upgrade` tracks: the
  `install-template` skill passes it and writes the stamp once the rest lands.

It exits 0 when the repo ends current (but for a stamp `--no-stamp` held back)
and 1 when files were left. It refuses
(exit 2) a repo stamped newer than the tool, a tracked file with uncommitted
changes (`--allow-dirty` overrides), and a prerelease of the tool itself
(`--prerelease` overrides), since that would stamp a release that never shipped.

`repotemplates stamp` writes the stamp alone, the last step after
`upgrade --no-stamp`:

```bash
repotemplates stamp path/to/repo --dry-run
repotemplates stamp path/to/repo
```

It sets `version` in `[tool.repotemplates]` to this release, keeps `omit` and
`keep`, writes the template's comment line in place of an old one (or above a
table written by hand), and renames a
`[tool.proj-template]` table. It refuses (exit 2) while `check` still reports
anything but the stamp behind, unless `--force`, and a repo stamped newer than
the tool or a prerelease of the tool, as `upgrade` does.

## Skills

The package ships two Claude Code and Codex skills: `install-template`
(scaffold a repo, or upgrade one to the template) and `install-renovatabot`
(enroll a repo in the self-hosted Renovate). Install them once:

```bash
repotemplates install            # stubs under ~/.claude/skills and ~/.agents/skills
repotemplates install --check    # ok, or what is missing or drifted
repotemplates skill install-template   # print a skill's instructions
```

Each stub runs `repotemplates skill <name>`, so the instructions an agent reads
always come from the installed release, and so does the template they apply:
`repotemplates path template` prints the directory the release ships.
`install --local` writes the stubs into the enclosing repo instead, calling
`uv run repotemplates`.

## Developing repotemplates

Working on the template itself needs only `uv` and `planners`. The root
`pyproject.toml` is the `repotemplates` CLI package (`src/repotemplates/`), and
its dev group supplies `pre-commit`, `shellcheck`, `pytest`, `ruff`, and
`pyrefly`:

```bash
uv sync
uv run pre-commit install --hook-type pre-commit --hook-type post-merge
```

Run the checks after changing `scripts/` or `template/`. The behavioral test
scaffolds from the checkout's HEAD, so commit first:

```bash
/bin/bash tests/portability.test.sh
/bin/bash tests/init.test.sh
git ls-files -co --exclude-standard -- '*.sh' | xargs uv run shellcheck
```

Run the Python checks after changing the CLI:

```bash
uv run ruff check . && uv run ruff format --check .
uv run pyrefly check
uv run pytest
```

After each release, regenerate the release manifest on `dev` and commit it:
`uv run python scripts/build_manifest.py`. CI fails until it lists the new tag.

## Template structure

```
MODULE__NAME/
├── __init__.py
├── cli.py
├── py.typed
tests/
├── __init__.py
├── test_MODULE__NAME.py
.planners/
├── README.md                  # generated plans index (planners CLI)
├── plans/
.claude/
├── CLAUDE.md
├── settings.json              # shared hooks (Stop: lint + type-check gate)
├── hooks/
│   └── lint-typecheck.sh
.github/
├── dependabot.yml             # or the Renovate pair, per --deps
├── renovate.json
├── workflows/
│   ├── test.yml
│   ├── publish.yml            # off until PUBLISH_ENABLED is true
│   └── renovate.yml
CHANGELOG.md
README.md
pyproject.toml
.gitignore
.gitattributes                 # .planners/README.md merge=union (planners index)
.pre-commit-config.yaml
.python-version
```
