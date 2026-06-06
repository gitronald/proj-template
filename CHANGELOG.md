# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Optional self-hosted Renovate dependency automation as a scaffold-time choice (`proj-init.sh --deps dependabot|renovate`, default `dependabot`). Choosing `renovate` ships `renovate.json` + a scheduled `renovate.yml` instead of `dependabot.yml`, with security-hardened defaults: `dev`-targeted PRs, per-ecosystem grouping, a 5-day release cooldown (`minimumReleaseAge` with `timestamp-required`), no auto-merge, no silent action-digest mutation in workflows, and a least-privilege GitHub App token so update PRs trigger CI. Dependabot remains the zero-setup default.

### Changed

- Disable the template's PyPI publish workflow by default; it now runs only when the `PUBLISH_ENABLED` repository variable is set to `true`.
- Move the template's `.claude` permission grants from the personal `settings.local.json` into the shared, committed `settings.json`, and stop shipping a `settings.local.json` (including its `.gitignore` negations).

## [0.4.0] - 2026-05-25

### Added

- Agentic lint/type-check integration for scaffolded projects: a committed `Stop` hook, a `CLAUDE.md` "before finishing a task" directive, a `lint-and-typecheck` skill, and a combined ruff + pyrefly guide.

### Changed

- Adopt the pyrefly v1.0 `strict` preset, relaxing `implicit-any` in `tests/` via a sub-config.
- Bump ruff-pre-commit to v0.15.14, and pin `pyrefly>=1.0.0` and `ruff>=0.15` in the template's dev dependencies.

## [0.3.2] - 2026-04-30

### Removed

- Drop GitHub issue templates from the project template.

## [0.3.1] - 2026-04-28

### Changed

- Bump GitHub Action versions (setup-uv 8.1.0, upload-artifact v7, and download-artifact v8).
- Run the pyrefly pre-commit hook as a local entry, and add typer as a template dependency.
- Ignore `.env` files in the template `.gitignore`.

## [0.3.0] - 2026-04-10

### Added

- Template infrastructure: publish workflow, Dependabot config, issue/PR templates, a `py.typed` marker, a Keep a Changelog template for scaffolded projects, and a trusted-publishers setup guide.

### Fixed

- Correct the publish workflow and Dependabot config.

## [0.2.0] - 2026-04-09

### Added

- Add the pyrefly type checker to the template.
- Add a pre-commit installation guide.

## [0.1.3] - 2026-04-01

### Fixed

- Fix cross-platform `sed -i` compatibility in `proj-init.sh`.

## [0.1.2] - 2026-03-30

### Added

- Add a `--branch` flag to `proj-init.sh` (defaults to `main`).

## [0.1.1] - 2026-03-30

### Added

- Initial release: a uv-based Python project template with a clone-based `proj-init.sh` scaffold script, license selection, VERSION tracking, and dev/main branch setup.
