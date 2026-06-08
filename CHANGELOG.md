# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.5.3] - 2026-06-08

### Changed

- Restrict the scaffolded project's sdist to the package and core files via `[tool.hatch.build.targets.sdist]` `only-include` (`/PACKAGE`, `/README.md`, `/CHANGELOG.md`, `/LICENSE`), keeping internal plan files (`.planners/`), guides (`docs/`), the `.claude/` directory, tests, and tooling out of the published sdist.

## [0.5.2] - 2026-06-08

### Added

- `renovatabot-enroll.sh` detects repository visibility and warns before enrolling a **private** repo, where the least-privilege App (no Contents permission) cannot read refs and the first Renovate run fails at init. Added a "Troubleshooting the first run" section to the GitHub automation guide mapping each failure stage to its setup gap.

### Fixed

- Align the enroll guide and skill with the script: drop the stale `--env-file` caveat (the script streams the key file) and correct the `.env` precondition to `RENOVATE_APP_PRIVATE_KEY_PATH`.

## [0.5.1] - 2026-06-08

### Changed

- Rename the self-hosted Renovate enrollment tooling to **renovatabot** to match the GitHub App — `scripts/renovatabot-enroll.sh`, the `renovatabot-enroll` skill, and the credentials directory `~/.config/renovatabot`. The enroll script now stores the App key as a path (`RENOVATE_APP_PRIVATE_KEY_PATH`) and streams the file into the secret, and gains `--dry-run` and `--yes` flags with a pre-change confirmation prompt.
- Expand the GitHub automation guide with the GitHub App install walkthrough and the exact App permissions Renovate needs: Dependabot-alerts read for security PRs, and Issues read-write for the dependency dashboard.

## [0.5.0] - 2026-06-06

### Added

- Optional self-hosted Renovate dependency automation as a scaffold-time choice (`proj-init.sh --deps dependabot|renovate`, default `dependabot`). Choosing `renovate` ships `renovate.json` + a scheduled `renovate.yml` instead of `dependabot.yml`, with security-hardened defaults: `dev`-targeted PRs, per-ecosystem grouping, a 5-day release cooldown (`minimumReleaseAge` with `timestamp-required`), no auto-merge, no silent action-digest mutation in workflows, and a least-privilege GitHub App token so update PRs trigger CI. Dependabot remains the zero-setup default.
- Maintainer tooling to enroll a scaffolded repo in self-hosted Renovate in one step: `scripts/renovatabot-enroll.sh <owner/repo>` (and the `renovatabot-enroll` skill) pushes the GitHub App secrets from a local `.env`, keeps Dependabot vulnerability alerts on while turning its security-update PRs off so only Renovate opens PRs (`--no-dependabot-toggle` to skip), and triggers the first Renovate run. Not shipped into scaffolded projects.

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
