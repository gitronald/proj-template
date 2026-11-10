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

`--source` still clones, so it scaffolds the source's committed tree: unpushed
commits are picked up, uncommitted edits are not. Without `--branch`, a local
checkout is cloned at whatever branch it has checked out; the script prints the
commit it used.

The script targets bash 3.2+, so it runs on stock macOS as well as Linux.

## What it does

1. Clones the template repo and replaces placeholders: `PROJECT__NAME` becomes your project name, and `MODULE__NAME` becomes its Python module name (dashes become underscores)
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

The `repotemplates` command compares a repo with the template. It is read-only:
it never edits a repo.

```bash
uv tool install repotemplates            # or run it once: uvx repotemplates check
repotemplates check                      # the repo in the current directory
repotemplates check path/to/repo --json  # one JSON object, for scripts
repotemplates check --repos-dir ~/repos  # every stamped clone, as one table
repotemplates version
```

Until it is on PyPI, install it from a release tag:
`uv tool install git+https://github.com/gitronald/repotemplates@vX.Y.Z`.

For each repo it reports:

- **The stamp**: `latest`, `behind` or `ahead` of the newest release the tool
  knows, `alpha`, `unknown`, or `missing`. Both `[tool.repotemplates]` and the
  older `[tool.proj-template]` are read.
- **Each template-owned file**: `current` (matches the template this release
  ships), `matches vX.Y.Z` (an earlier release), `one-off` (matches no release),
  `missing`, or `retired` (a file the template no longer ships, still present).
  Claude hook scripts (`.claude/hooks/*.sh`) are compared by exact content, and
  the `hooks` block of `.claude/settings.json` as normalized JSON, other keys
  ignored.
- **Git state of the Claude settings files**: tracked, ignored, untracked, or
  absent. An ignored file never reaches a fresh clone or a cloud session; the
  template ignores `.claude/` by default, so this is information, not drift.

It exits 0 when the stamp is the latest and every file is current, 1 when
anything differs or `--repos-dir` finds no repo to check, and 2 on a usage
error. `--markdown` prints Markdown tables.
With `--repos-dir`, `--json` prints an array, and `*-archive` repos and repos
with no stamp are skipped unless `--include-archived` or `--all` is given.

The tool carries the template and a manifest of every release's files, so it
needs no clone and no network.

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

## Future

- Support GitHub's [template repository](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-template-repository) feature via `gh repo create --template` to replace the clone step

## Template structure

```
MODULE__NAME/
├── __init__.py
├── cli.py
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
├── workflows/test.yml
README.md
pyproject.toml
.gitignore
.gitattributes                 # .planners/README.md merge=union (planners index)
.pre-commit-config.yaml
.python-version
```
