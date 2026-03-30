# proj-template

Python project template with uv, ruff, pytest, pre-commit, GitHub Actions CI, and stanza release automation.

## Quick Start

Download and run the scaffold script to create a new project:

```bash
curl -s https://raw.githubusercontent.com/gitronald/proj-template/dev/scaffold.sh | bash -s <path>
```

Or add an alias to your `.bashrc` or `.zshrc`:

```bash
alias new-proj='curl -s https://raw.githubusercontent.com/gitronald/proj-template/dev/scaffold.sh | bash -s'
```

Then create a new project:

```bash
new-proj ~/repos/myproject
```

## What it does

1. Copies the template and replaces `PACKAGE` placeholders with your project name
2. Initializes a git repo on a `dev` branch
3. Installs dependencies with `uv sync`
4. Sets up pre-commit hooks and stanza
5. Makes the initial commit

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
