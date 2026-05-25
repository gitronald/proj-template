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
- Type checking: pre-commit hooks run pyrefly on commit (strict preset)
- CI: GitHub Actions runs lint + type check + test matrix (Python 3.11–3.14) on push/PR to dev/main
- See `docs/guides/lint-and-typecheck.md` for the full ruff + pyrefly workflow

## Before finishing a task

Run both checks at the project root and fix all reported errors before
completing a task:

```bash
uv run ruff check .
uv run pyrefly check
```

A `Stop` hook (`.claude/hooks/lint-typecheck.sh`) enforces this automatically,
but run them yourself as you work — don't wait for the hook to surface errors.

## Release Automation

Use [stanza](https://github.com/gitronald/stanza) for release workflows:

```bash
stanza release [patch|minor|major|prerelease]
stanza init
```
