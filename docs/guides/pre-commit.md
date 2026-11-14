# Pre-commit

Projects created from this template include a [pre-commit](https://pre-commit.com/) configuration that runs [ruff](https://docs.astral.sh/ruff/) formatting and linting on every commit.

## Hooks

The `.pre-commit-config.yaml` configures two hooks from [ruff-pre-commit](https://github.com/astral-sh/ruff-pre-commit):

- **ruff-format** — auto-formats staged Python files
- **ruff-check** — lints staged Python files and auto-fixes what it can (`--fix`)

Both hooks run only on staged files, so they are fast and scoped to what you are committing.

Three local hooks run through `uv run`:

- **pyrefly-check** — type-checks the project when Python files are staged
- **planners-validate** — validates the frontmatter of staged `.planners/plans/*/plan.md` files
- **planners-index** — regenerates `.planners/README.md` after a merge (`post-merge` stage)

`default_stages: [pre-commit]` keeps every other hook off the `post-merge` stage, so a merge runs only `planners-index`.

## Installation

If you scaffolded your project with `init.sh`, pre-commit is already installed. To set it up manually:

```bash
uv sync --all-groups   # installs pre-commit into the dev dependency group
uv run pre-commit install --hook-type pre-commit --hook-type post-merge   # registers both git hooks
```

The `post-merge` hook type carries `planners-index`, which regenerates `.planners/README.md` after a merge. A plain `pre-commit install` registers only `pre-commit`, so that hook would never run.

Verify the hooks are registered:

```bash
ls .git/hooks/pre-commit .git/hooks/post-merge
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
uv run pre-commit run ruff-check --all-files
```

## Updating hook versions

The hook installs its own ruff at the pinned `rev`, while CI and the Stop hook run
the ruff in `uv.lock`. When the two differ, a commit can pass the hook and then fail
`ruff format --check` in CI, so the `rev` always equals the locked ruff.

Dependabot's `uv` ecosystem bumps the lock and nothing bumps the rev, so after a
lock update, set the rev to the locked version (`uv run ruff --version`).
`repotemplates check` reports the pair as its own row (`ruff rev vs uv.lock`), and
`repotemplates upgrade` moves the rev for you.

To move both to a newer ruff, set the rev and relock to exactly that version:

```bash
uv run pre-commit autoupdate --repo https://github.com/astral-sh/ruff-pre-commit
uv lock --upgrade-package ruff==<version>   # the version the rev now names
```

A bare `--upgrade-package ruff` takes the newest release, which may not be the
rev's. When the rev moves to a new minor, widen the `ruff>=X.Y,<X.Z` range in the
`dev` group first.

Then commit `.pre-commit-config.yaml` and `uv.lock` (and `pyproject.toml`, when the
range moved).

## Ruff configuration

Ruff settings are defined in `pyproject.toml` under `[tool.ruff]` and `[tool.ruff.lint]`. The template enables these rule sets:

- **F** — pyflakes
- **E** — pycodestyle errors
- **W** — pycodestyle warnings
- **I** — isort (import sorting)
- **UP** — pyupgrade (modern Python idioms)

`ruff format` also formats Python code fences in Markdown, and the `ruff-format` hook runs on
`.md` files. `extend-exclude = [".planners/", "CHANGELOG.md"]` keeps it off plans and the
changelog, which quote code as it was; README and `docs/` fences are formatted.
