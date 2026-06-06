# GitHub Automation

Projects created from this template include GitHub-side automation in
[`.github/`](../../template/.github/) — continuous integration, dependency updates, and
packaging. This guide is the canonical reference for what ships and why; the config files
point back here.

| File | Trigger | What it does |
|------|---------|--------------|
| [`workflows/test.yml`](../../template/.github/workflows/test.yml) | Push or PR to `dev` or `main` | Installs deps with `uv`, then runs ruff lint, `ruff format --check`, `pyrefly check`, and `pytest --cov` across Python 3.11–3.14 |
| [`workflows/publish.yml`](../../template/.github/workflows/publish.yml) | Push of a `v*` tag | Builds the wheel and publishes to PyPI via Trusted Publishing — skipped unless the `PUBLISH_ENABLED` repository variable is `true` |
| [`dependabot.yml`](../../template/.github/dependabot.yml) | Weekly | Grouped dependency updates for the `uv` and `github-actions` ecosystems (one PR per ecosystem) |

## Tests (`test.yml`)

CI runs on every push and pull request targeting `dev` or `main`. It installs the project
with `uv` and runs the full quality gate — ruff lint, `ruff format --check`, `pyrefly check`,
and `pytest --cov` — across the Python 3.11–3.14 matrix. The same format and lint checks run
locally on each commit via [pre-commit](pre-commit.md).

## Publish (`publish.yml`)

Tag pushes (`v*`) build the wheel and publish to PyPI via Trusted Publishing (OIDC, no stored
tokens). It is disabled by default until you opt in. See [Trusted Publishers](trusted-publishers.md)
for the full setup — the PyPI publisher, the `pypi` environment, and the `PUBLISH_ENABLED` switch.

## Dependency updates (`dependabot.yml`)

Dependabot opens dependency-update PRs weekly, **grouped per ecosystem** — each run yields at
most one PR for `uv` (Python) deps and one for `github-actions`, not one PR per package.
Grouping only takes effect once `dependabot.yml` reaches the repository's **default branch**
(Dependabot reads its config from there).

Dependabot vulnerability **alerts** are a separate, repo-level setting independent of this file —
leave them enabled for the native advisory surface.

## Planned: migration to Renovate

A planned change replaces Dependabot's *updates* role with [Renovate](https://docs.renovatebot.com)
for stronger grouping, a release cooldown, `dev`-targeted PRs, and ongoing action SHA-pinning —
with supply-chain hardening as the focus. When it lands, this guide becomes the decision record
(motivation, options, final choice). See the [add-renovate plan](../plans/003-add-renovate.md).

> **Known gap:** the template's workflows currently pin actions to mutable tags (`@v6`,
> `@release/v1`); moving them to commit SHAs is part of the Renovate work.
