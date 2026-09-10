# proj-template

Python project template with uv, ruff, pyrefly, pytest, pre-commit, GitHub Actions CI, and stanza release automation.

## Quick Start

Download and run the scaffold script to create a new project:

```bash
curl -s https://raw.githubusercontent.com/gitronald/proj-template/main/scripts/proj-init.sh | bash -s <path>
```

Or add an alias to your `.bashrc` or `.zshrc`:

```bash
alias proj-init='curl -s https://raw.githubusercontent.com/gitronald/proj-template/main/scripts/proj-init.sh | bash -s'
```

Then create a new project:

```bash
proj-init ~/repos/myproject
proj-init --license apache-2.0 ~/repos/myproject
proj-init --source ~/repos/proj-template ~/repos/myproject   # scaffold from a local checkout or fork
```

`--source` still clones, so it scaffolds the source's committed tree: unpushed
commits are picked up, uncommitted edits are not.

The script targets bash 3.2+, so it runs on stock macOS as well as Linux.

## What it does

1. Clones the template repo and replaces placeholders: `PROJECT__NAME` becomes your project name, and `MODULE__NAME` becomes its Python module name (dashes become underscores)
2. Stamps the template release it used into `[tool.proj-template]` in the new repo's `pyproject.toml`, so you can later tell which template version a repo carries (see [Template version stamp](#template-version-stamp))
3. Fetches a LICENSE file from GitHub's API (default: MIT)
4. Initializes a git repo on a `dev` branch
5. Installs dependencies with `uv sync`
6. Sets up pre-commit hooks and stanza
7. Makes the initial commit

## Template version stamp

Every scaffolded repo records the template release it came from:

```toml
[tool.proj-template]
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

To audit drift across repos:

```bash
grep -A1 '\[tool.proj-template\]' ~/repos/*/pyproject.toml
```

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
├── settings.local.json        # permission allow/deny/ask lists (machine-local)
├── hooks/
│   └── lint-typecheck.sh
.github/
├── workflows/test.yml
README.md
pyproject.toml
.gitignore
.pre-commit-config.yaml
.python-version
```
