# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed

- `proj-init.sh` no longer breaks when your GitHub display name contains a sed metacharacter. The
  name is fetched with `gh api user --jq .name` and substituted into the LICENSE body, so a name
  like "Ada / Lovelace" aborted the scaffold mid-run (`set -e` on a failed `s///`) and one like
  "Smith & Co" silently wrote `[fullname]` into the license instead of the name. Escaping is now
  centralized in a `sed_escape` helper, which the version stamp added in 0.9.0 also uses.

## [0.9.0] - 2026-09-09

### Added

- Scaffolded repos now carry a `[tool.proj-template]` table in `pyproject.toml` recording the
  template release they came from, so template drift is auditable from inside each repo without a
  central registry or a new file. `proj-init.sh` stamps it from the *cloned* `VERSION` rather than
  the local checkout's, so `--branch dev` records the prerelease actually applied. The table is
  inert to package consumers: build backends translate only `[project]`, so it never reaches the
  wheel or the PyPI metadata.
- `install-template` gained a matrix row and note for re-stamping the version on upgrade, including
  the rule that a partial upgrade must not stamp the newer release.

### Changed

- The sdist `only-include` comment in `template/pyproject.toml` no longer implies the list is
  exhaustive: hatchling force-includes `pyproject.toml`, `PKG-INFO`, and `.gitignore` in every
  sdist regardless of the list, and neither `exclude` nor `ignore-vcs` drops them.

## [0.8.5] - 2026-09-09

### Changed

- `docs/guides/github-automation.md` now states why the config files link back to it as absolute
  GitHub URLs rather than relative paths — `docs/` sits outside `template/`, so a scaffolded repo
  gets the configs but never the guide — along with the editing rule that follows from it (thin
  comments in the configs, rationale in the guide) and what to grep if the guide is ever moved.
  `template/.github/workflows/renovate.yml` was the one back-link still written as a bare
  `docs/guides/github-automation.md` path, unresolvable in the repos that receive it; it now
  carries the same absolute URL as `dependabot.yml` and `renovate.json`.
- `template/.github/dependabot.yml` lost its `target-branch` rationale comment, which restated the
  guide's Dependabot section (the options-reference quote, the manifest-scan scoping, the
  security-updates caveat) in full. The header keeps the guide link — absolute, since a scaffolded
  repo has no local `docs/` copy — plus a two-line note that Dependabot reads the file from the
  default branch only, the one fact that makes an edit to this file silently do nothing and so
  worth having where the edit happens.
- The template's Claude permissions moved out of `.claude/settings.json` into a new
  `.claude/settings.local.json`, leaving `settings.json` to carry only the shared `Stop` hook.
  `settings.local.json` is the file Claude Code writes machine-local permission grants to, so
  scaffolded repos now accumulate their own grants in the same file the template seeds — and it
  stays untracked in every target (`.claude/` is gitignored there) while proj-template tracks its
  copy as the payload upgrades ship from. `git push` also moved from `ask` to `allow`.
- `install-template` skill: the `.claude/settings*.json` row is now ask-first and exempt from the
  "stale template content replaces silently" path. A target's `settings.local.json` diverges by
  design — Claude Code appends every grant the user accepts there — so an upgrade must show what
  adopting the template's copy would change (entries added, entries removed, and entries that move
  between `allow`/`ask`/`deny`, each with its direction) rather than overwriting grants the user
  chose. Moves need their own approval; hook `command`/`timeout` changes in `settings.json` stay
  silent-replace, since those are template-owned plumbing.
- The template's `test.yml` now passes `--python ${{ matrix.python-version }}` to `uv sync` as well
  as setting the job-level `UV_PYTHON`. The flag is redundant — `UV_PYTHON` already governs that
  step and every bare `uv run` after it — but the sync step is the one whose interpreter choice the
  rest of the job inherits, so restating it there means a copied-out sync line, or an edit that
  drops the `env` block, keeps testing the intended interpreter instead of silently falling back to
  `.python-version` and running the same Python in every matrix cell. A comment records that the
  restatement is deliberate, so a later reader does not "clean it up".
- `install-template` skill: the `test.yml` sync row and reconcile notes now cover the `--python`
  flag on `uv sync` alongside the `UV_PYTHON` env pin, with an explicit "don't simplify this away"
  note. Without it the flag reads as redundant on inspection — which it is — and an upgrade that
  tidied it out would leave the repo one `env`-block edit away from the silently-no-op matrix the
  neighbouring note already warns about.
- Template pinned version bumped: `astral-sh/setup-uv` v9.0.0 -> v10.0.1, in both `test.yml` and
  `publish.yml`. v10's breaking change disables `enable-cache: auto` for the `pull_request_target`,
  `workflow_run`, and `release` events; neither template workflow uses those triggers (`test.yml`
  runs on `push`/`pull_request`, `publish.yml` on `push: tags`), so nothing changes for a scaffolded
  repo beyond picking up v10's checksum-verification and manifest-timeout fixes.

## [0.8.4] - 2026-09-09

### Fixed

- The template's `dependabot.yml` now sets `target-branch: dev` for both ecosystems, so
  dependency-update PRs open against the active branch instead of the default one. Previously they
  targeted `main`, so every batch had to be retargeted by hand before it could merge into `dev`, and
  Dependabot resolved manifests against `main` rather than the tree the updates would merge into.
  The `github-automation` guide claimed this was a Dependabot limitation ("it can't target `dev`
  directly") and used it to motivate the Renovate option; that was incorrect — `target-branch` is a
  supported option and GitHub documents this exact use case. The guide now states the real
  constraint instead: `dependabot.yml` is read from the default branch, so edits to it stay inert
  until they reach `main`. Renovate's other advantages (no silent digest mutation, fail-closed
  cooldown, no auto-merge) are unaffected.
- `install-template` skill: the `dependabot.yml` sync row now reconciles `target-branch`
  alongside `groups` and `cooldown`, so a repo upgraded from an older template revision picks
  up the change above instead of silently keeping PRs pointed at the default branch. The
  accompanying note gates the edit on the repo actually having a `dev` branch — scaffolded
  repos always do, but an older or non-template repo may not, and pointing Dependabot at a
  missing branch stops its updates.

## [0.8.3] - 2026-09-08

### Changed

- Template pinned version bumped: the `ruff-pre-commit` hook to v0.16.6.

## [0.8.2] - 2026-09-08

### Changed

- `install-template` skill: the upgrade path now triages every managed file by diffing it against `template/` before applying a sync-matrix row, instead of treating "the file exists" as satisfied. A file that is absent or identical is applied silently; one that diverges but carries nothing the template lacks is replaced and reported (the repo is simply on an older template revision); one that carries content the template would drop or change — a customized value, an extra entry, a different command or timeout — is put to the user before being touched. Those questions are gathered across the whole matrix and asked in a single batched round offering replace / merge / keep, with the answers recorded in the upgrade plan's Log so the next upgrade does not re-litigate them.

### Fixed

- The template's `Stop` hook now runs `ruff format --check .` alongside `ruff check` and `pyrefly`, mirroring the checks the test workflow enforces. The linter does not police layout — quote style, wrapping, trailing-comma expansion — so the gate previously stayed green on code CI would reject.
- The template's `Stop` hook now resolves paths independently of the agent's working directory. `.claude/settings.json` invokes the hook through `${CLAUDE_PROJECT_DIR:-.}` rather than a relative path, which previously failed whenever the agent's directory was not the project root, and `lint-typecheck.sh` walks up from the working directory to the nearest `pyproject.toml` before running `ruff` and `pyrefly` — so work inside a git worktree under `.worktrees/` is checked against that worktree's own tree and `.venv`, not the main checkout — falling back to `CLAUDE_PROJECT_DIR` when the directory sits outside any project.

### Security

- Raise the template's `pytest` dev-dependency floor to `>=9.0.3`, past GHSA-6w46-j5rx-g56g (insecure `/tmp/pytest-of-{user}` tmpdir handling, affecting `< 9.0.3`). The previous `>=9.0.2` floor resolved to a safe version in practice but permitted a vulnerable one.

## [0.8.1] - 2026-09-06

### Changed

- Template workflows (`test.yml`, `publish.yml`, `renovate.yml`) now ship actions pinned to commit SHAs with a `# vX.Y.Z` comment (e.g. `actions/checkout@3d3c42e…  # v7.0.1`) instead of bare version tags. This reverses the 0.6.0 switch to tags, which assumed Dependabot would not keep SHA pins current; in practice Dependabot bumps the SHA and the comment together, as observed in a downstream repo that had re-pinned to SHAs. The `install-template` skill now syncs pins to the template's SHAs and converts bare tags on upgrade, and the `install-renovatabot` skill and the GitHub automation guide describe `helpers:pinGitHubActionDigests` as a backstop for newly added actions rather than the step that introduces SHA pins; the TestPyPI snippet in the trusted-publishers guide uses the same pinned form.
- GitHub automation guide: drop the stale claim that Dependabot has no release cooldown (the template has configured one since 0.6.2).

## [0.8.0] - 2026-09-05

### Added

- Coverage configuration in the template `pyproject.toml`: `pytest` now runs with `--cov` by default via `addopts`, and a `[tool.coverage]` section sets the package as `source`, enables branch coverage, excludes common boilerplate lines, and enforces a `fail_under = 50` floor that projects can raise. The test workflow runs plain `uv run pytest` and inherits the same settings. The scaffolded placeholder test now invokes the CLI through `typer.testing.CliRunner` so a fresh project starts above the floor. The `install-template` sync matrix merges `[tool.coverage.*]` into upgraded repos.
- Plan 006 (parked): options for publishing coverage to Codecov, Coveralls, or a workflow artifact.

### Changed

- `install-template` skill: apply the gitignored `.claude/*` payload in the main checkout rather than the upgrade worktree, where it would vanish on removal; pin `fail_under` to an existing repo's current total; prefer bare `--cov` over `--cov=<pkg>`; and refresh the template-owned `## Development` bullets in an existing `.claude/CLAUDE.md` instead of never touching its content.
- `test-proj-init` skill: assert the scaffold's coverage table lists the renamed module and reports the floor as reached.

## [0.7.0] - 2026-08-09

### Added

- `test-proj-init` repo skill: end-to-end verification of `proj-init.sh` — scaffold a dash-named project (exercising the `PROJECT`/`MODULE` placeholder split), verify placeholders, build, CLI, tests, and GitHub repo state, with a local-only mode that creates no repo.

### Changed

- `proj-init.sh` now installs `planners` as a global uv tool when it is missing — the scaffolded pre-commit hook shells out to `planners` on PATH, so a fresh machine no longer fails its first commit.
- Template pinned versions bumped: `actions/checkout` v7.0.1, `astral-sh/setup-uv` v9.0.0, `pypa/gh-action-pypi-publish` v1.14.2, `renovatebot/github-action` v46.2.1, and the ruff pre-commit hook v0.16.1.
- GitHub automation guide: document the **Commit statuses** permission Renovate needs to record the `minimumReleaseAge` cooldown status, the optional **Administration: read** scope (automerge-only — skip it by default), and rework first-run troubleshooting as a cascade of permission gaps rather than three independent stages.

### Fixed

- `proj-init.sh`: dashed project names (e.g. `my-tool`) no longer break the scaffold. The template now uses two placeholders — `PROJECT` for the project/repo name and `MODULE` for the Python module name — and the script derives the module name by mapping dashes to underscores, validating it before scaffolding. Previously a dashed name produced an invalid module directory and `uv sync` failed hatchling's wheel file-selection heuristic mid-scaffold.

- Template `dependabot.yml`: drop `semver-major-days` from the `github-actions` cooldown. The granular `semver-*-days` cooldown subkeys are invalid for the `github-actions` ecosystem — GitHub rejects the entire config on one, silently disabling Dependabot (no PRs). `default-days` stays on `github-actions`; `uv` keeps both. (The 0.6.2 entry below set it on both ecosystems; only `uv` is valid.)

## [0.6.3] - 2026-06-21

### Changed

- `install-template`: the upgrade sync matrix now reconciles each managed file's *inner* config against `template/`, not just its presence. The `test.yml` row calls out the job-level `UV_PYTHON` env pin (without it a multi-version matrix silently tests one interpreter), and the `dependabot.yml` row reconciles each ecosystem's `groups` and `cooldown` blocks.
- `install-template`: document the intentional Dependabot repo-settings policy — alerts on, security updates (`automated-security-fixes`) off — so scheduled version-update PRs plus the release-time advisory audit stay the update path, with alerts kept on purely as a warning layer.

## [0.6.2] - 2026-06-21

### Added

- `install-template` upgrade mode now relocates misplaced config files: when a template-managed file (e.g. a root-level `CLAUDE.md`) is genuinely the right file but in an old spot, it is `git mv`'d to the canonical path before syncing, instead of being left or duplicated. Documents that tracking `.claude/` is a per-repo decision and the `.claude/*` + `!.claude/CLAUDE.md` pattern for keeping one file tracked.
- Template `dependabot.yml` now sets a release `cooldown` (`default-days: 5`, `semver-major-days: 14`) on both the `github-actions` and `uv` ecosystems, so dependency-update PRs wait for a release to season before opening.

### Fixed

- `install-template` upgrade mode now uses the conventional `.worktrees/template-upgrade` path (and `.worktrees/` gitignore entry) instead of `.claude/worktrees/`.

## [0.6.1] - 2026-06-10

### Changed

- The `install-template` skill's upgrade mode now runs through the planners lifecycle: scaffold/activate a plan in the target repo, work in a worktree at `.claude/worktrees/template-upgrade`, open a PR into `dev`, and close the plan on merge (index regen, worktree removal, pre-commit hook re-install check).

### Fixed

- Template `test.yml` matrix was false green: bare `uv run` re-resolves to the `.python-version` pin (3.14), so every matrix cell ran the same interpreter regardless of `uv sync --python`. A job-level `UV_PYTHON: ${{ matrix.python-version }}` now outranks the pin, so each cell tests its own Python.

## [0.6.0] - 2026-06-10

### Added

- `install-template` skill: scaffold a new repo from the template, or upgrade an existing repo to the latest standard via a per-file sync matrix that adapts to repo type (publishable package vs app/site), requiring green ruff/pyrefly/pre-commit checks before the Claude Stop hook lands.

### Changed

- Migrate this repo's plan tracking to the `.planners/` layout: plans moved to `.planners/plans/<NNN>-<slug>/plan.md` with a generated `.planners/README.md` index, `TODO.md` retired, and a `planners-validate` pre-commit hook.
- Template scaffold now stamps the `.planners/` layout instead of `docs/` + `TODO.md`: empty plans index, `plans/.gitkeep`, and the `planners-validate` hook block in the generated `.pre-commit-config.yaml`.
- Move `template/CLAUDE.md` into `template/.claude/`, and ignore `.claude/` in the template `.gitignore` so generated repos receive the Claude payload on disk but never track it; expand the template ignore entries (`.worktrees/`, `build/`, `dist/`, coverage files).
- Fold the per-repo `lint-and-typecheck` skill and guide into the machine-global skill — the template no longer ships `docs/guides/lint-and-typecheck.md` or `.claude/skills/lint-and-typecheck/`.
- Move `proj-init.sh` into `scripts/` — the raw-URL alias changes to `scripts/proj-init.sh`.
- Ship workflow actions pinned to specific version tags (e.g. `actions/checkout@v6.0.3`) instead of commit SHAs so Dependabot, the default updater, keeps them current; Renovate enrollment re-pins to SHA digests via `helpers:pinGitHubActionDigests`.
- Rename the `renovatabot-enroll` skill to `install-renovatabot` (script name unchanged) and document the SHA-pinning handoff in the skill and the GitHub automation guide.

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
