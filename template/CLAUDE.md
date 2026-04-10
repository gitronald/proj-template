# Claude Settings

This file provides guidance to [Claude Code](claude.ai/code).

## Package Structure

```
PACKAGE/
├── cli.py              # Typer CLI entry point
└── __init__.py
```

## Development

- Install: `uv sync --all-groups`
- Tests: `uv run pytest`
- Linting: pre-commit hooks run ruff format + lint on commit
- Type checking: pre-commit hooks run pyrefly on commit
- CI: GitHub Actions runs lint + type check + test matrix (Python 3.11–3.14) on push/PR to dev/main

## Release Automation

Use [stanza](https://github.com/gitronald/stanza) for release workflows:

```bash
stanza release [patch|minor|major|prerelease]
stanza init
```
