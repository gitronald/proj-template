# proj-template

Python project template with uv, ruff, pytest, pre-commit, GitHub Actions CI, and stanza release automation.

## Quick Start

Download and run the scaffold script to create a new project:

```bash
curl -s https://raw.githubusercontent.com/gitronald/proj-template/main/proj-init.sh | bash -s <path>
```

Or add an alias to your `.bashrc` or `.zshrc`:

```bash
alias proj-init='curl -s https://raw.githubusercontent.com/gitronald/proj-template/main/proj-init.sh | bash -s'
```

Then create a new project:

```bash
proj-init ~/repos/myproject
proj-init --license apache-2.0 ~/repos/myproject
```

## What it does

1. Clones the template repo and replaces `PACKAGE` placeholders with your project name
2. Fetches a LICENSE file from GitHub's API (default: MIT)
3. Initializes a git repo on a `dev` branch
4. Installs dependencies with `uv sync`
5. Sets up pre-commit hooks and stanza
6. Makes the initial commit

## Future

- Support GitHub's [template repository](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-template-repository) feature via `gh repo create --template` to replace the clone step

## Template structure

```
PACKAGE/
├── __init__.py
├── cli.py
tests/
├── __init__.py
├── test_PACKAGE.py
docs/
├── README.md
├── guides/
├── plans/
.claude/
├── settings.local.json
.github/
├── workflows/test.yml
CLAUDE.md
README.md
TODO.md
pyproject.toml
.gitignore
.pre-commit-config.yaml
.python-version
```
