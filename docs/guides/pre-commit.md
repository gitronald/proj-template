# Pre-commit

Projects created from this template include a [pre-commit](https://pre-commit.com/) configuration that runs [ruff](https://docs.astral.sh/ruff/) formatting and linting on every commit.

## Hooks

The `.pre-commit-config.yaml` configures two hooks from [ruff-pre-commit](https://github.com/astral-sh/ruff-pre-commit):

- **ruff-format** — auto-formats staged Python files
- **ruff** — lints staged Python files and auto-fixes what it can (`--fix`)

Both hooks run only on staged files, so they are fast and scoped to what you are committing.

## Installation

If you scaffolded your project with `proj-init.sh`, pre-commit is already installed. To set it up manually:

```bash
uv sync --all-groups   # installs pre-commit into the dev dependency group
uv run pre-commit install   # registers the git hook in .git/hooks/pre-commit
```

Verify the hook is registered:

```bash
ls .git/hooks/pre-commit
```

## Usage

Once installed, the hooks run automatically on `git commit`. No extra steps needed.

To run the hooks manually against all files (useful after changing ruff settings):

```bash
uv run pre-commit run --all-files
```

To run a specific hook:

```bash
uv run pre-commit run ruff-format --all-files
uv run pre-commit run ruff --all-files
```

## Updating hook versions

To update ruff-pre-commit to the latest release:

```bash
uv run pre-commit autoupdate
```

Then commit the updated `.pre-commit-config.yaml`.

## Ruff configuration

Ruff settings are defined in `pyproject.toml` under `[tool.ruff]` and `[tool.ruff.lint]`. The template enables these rule sets:

- **F** — pyflakes
- **E** — pycodestyle errors
- **W** — pycodestyle warnings
- **I** — isort (import sorting)
- **UP** — pyupgrade (modern Python idioms)
