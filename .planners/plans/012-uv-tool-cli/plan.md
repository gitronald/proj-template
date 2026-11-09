---
id: 12
slug: uv-tool-cli
status: implemented
branch: feature/012-uv-tool-cli
created: 2026-11-09T15:21:39-08:00
concluded:
pr: https://github.com/gitronald/repotemplates/pull/60
---

# Package repotemplates as a uv tool for init and template checks

## Plan

### Goal

Make repotemplates installable as a uv tool:

```bash
uv tool install git+https://github.com/gitronald/repotemplates@vX.Y.Z
```

Give it a command line that scaffolds a repo and checks an existing repo
against the template:

| Command | What it does |
|---|---|
| `repotemplates init <path>` | scaffold a new repo, as `scripts/init.sh` does today |
| `repotemplates check [<repo>]` | report how a repo's template-owned files compare with the template: read-only, `--json` for scripts |
| `repotemplates check --repos-dir <dir>` | the same across every clone under a directory, as one table |
| `repotemplates version` | the installed release |

### Why

Knowing what the template ships, and which release shipped it, is the
template's own knowledge. Today a consumer has no way to ask for it.

- **Hand checks today:** an audit of the Claude Code hooks across the repos
  scaffolded from the template hashed each repo's `.claude/hooks/*.sh` against
  every release tag, to name the release each copy matched.
- **Why not elsewhere:** a general settings or hooks inventory tool could do
  that comparison, but only by reading this repo's `template/` and its tags. That
  would tie an unrelated tool to the template's layout. The check belongs here,
  beside the files it compares against.
- **Upgrades:** the `install-template` skill's upgrade mode works out the same
  facts by hand at every upgrade (preflight, the sync matrix). A `check` command
  gives it the mechanical part, and the skill keeps the judgment.

### Decisions

1. **Ship the template in the package.** `template/` is package data, so `init`
   and `check` work from the installed release with no clone and no network.
2. **Ship a per-release manifest.** It maps each template-owned path to its
   content hash in every release, so `check` can name the release a file
   matches. It is generated from the git tags by a script run at release time,
   and committed as package data. A missing manifest entry means "matches no
   release", the one-off case.
3. **Keep `VERSION` as the single version source.** stanza already bumps it. The
   build backend reads it (hatchling's version source), so the package version
   and the stamp written into scaffolded repos cannot disagree.
4. **The root `pyproject.toml` becomes the package.** Its header today says the
   repo is dev tooling only, not a package. `template/pyproject.toml` stays the
   scaffold's own file, placeholders and all.
5. **`check` is read-only.** It never edits a repo. Changing files stays with the
   `install-template` skill, at least until question 4 is answered.

### What `check` reports

For each repo:

- the stamp from `[tool.repotemplates]` (or the older `[tool.proj-template]`),
  and whether it is the latest release, behind it, an alpha, or missing
- for each template-owned file:
  - `current`: matches the latest release
  - `matches vX.Y.Z`: an older release
  - `one-off`: matches no release
  - `missing`, or `absent by design`: an optional file the repo opted out of
- whether each Claude settings file is tracked, ignored, or untracked, since an
  ignored hook does not reach a fresh clone or a cloud session

Comparison by file class, starting with the first two:

| Class | Paths | Compared by |
|---|---|---|
| Claude hook scripts | `.claude/hooks/*.sh` | exact content hash |
| Claude hook entries | the `hooks` block of `.claude/settings.json` | normalized JSON, other keys ignored |
| pre-commit config | `.pre-commit-config.yaml` | hook ids and revs (question 5) |
| CI workflows | `.github/workflows/*.yml` | exact hash (question 5) |
| ignore rules | `.gitignore` | the template's lines present, extras allowed (question 5) |

Exit status: 0 when everything is current, 1 when anything differs, and 2 for a
usage error. `--json` prints one object per repo. Without it, the command prints
an aligned table, or `--markdown`.

### Order

a. **Package skeleton.** Root `pyproject.toml` with a `repotemplates` console
   script, `version` reading `VERSION`, and `template/` as package data. Confirm
   with `uv tool install .`. stanza's release flow is unchanged.
b. **Release manifest.** Add the script that hashes the template-owned files at
   every tag, the committed manifest, and a test that the manifest covers the
   current `template/`. Wire regeneration into the release steps.
c. **`check` for one repo.** Report the stamp and the first two file classes.
   Add pytest coverage with fixture repos: current, one release behind, one-off,
   and settings ignored.
d. **`check --repos-dir`.** The fleet table, skipping `*-archive` and non-template
   repos (no stamp) unless asked.
e. **`init`.** Run or port `scripts/init.sh` (question 1). The curl-to-bash path
   in the README keeps working.
f. **Docs and the skill.** Update the README, `docs/guides/`, and the
   `install-template` preflight to read `repotemplates check --json`. Then a
   minor release.

Steps a to d are the first deliverable. Step e can follow in a later release.

### Open questions

1. Does `init` port `scripts/init.sh` to Python, or call the bash script it
   ships? The bash script supports a fresh machine with no uv (curl to bash),
   which the tool cannot replace.
2. Before or after plan 011 (multiple templates)? 011 moves `template/` to
   `templates/<name>/` and adds a `template` key to the stamp, which `check` has
   to read. Doing this first means `check` learns the layout twice. Doing 011
   first delays the check.
3. Distribution: install from a git tag only, or also PyPI? The publish workflow
   is gated off by default, and the name's availability on PyPI is unchecked.
4. Does upgrade become a command (`repotemplates upgrade`, applying the
   mechanical part of the sync matrix), or stay in the skill, informed by
   `check`?
5. Which file classes beyond the Claude hooks are template-owned for `check`'s
   purposes: pre-commit config, CI workflows, `.gitignore`? Where do repos
   legitimately diverge, so `check` reports drift rather than noise?

### Out of scope

- Changing what the template ships. This plan only makes it checkable.
- Running upgrades across many repos. A fleet pass uses `check` but lives with
  whoever runs the fleet.

## Log

- **2026-11-09T15:25:30-08:00** — Activated.
  - Branch: `feature/012-uv-tool-cli`
  - Base: `dev` at `d0da62c`
  - Worktree: `.worktrees/012-uv-tool-cli`
  - PR: pending
- **2026-11-09T15:35:09-08:00** — PR opened: https://github.com/gitronald/repotemplates/pull/60
- **2026-11-09T15:35:32-08:00** — Steps a to d built and pushed; step e (init) and the skill half of step f are left for a later release, as the plan allows.
  - Question 3 answered 2026-11-09: publish to PyPI, so `uv tool install repotemplates` and `uvx repotemplates` work. The name was free on 2026-11-09 (`pypi.org/pypi/repotemplates/json` and `repo-templates` both 404). `.github/workflows/publish.yml` is the template's gated workflow; it does nothing until the owner adds the PyPI pending publisher and sets `PUBLISH_ENABLED`.
  - Question 2 answered 2026-11-09: this plan went first. The template's location is resolved in one function, `paths.template_root()`, so plan 011 changes that function and teaches `read_stamp` the stamp's `template` key.
  - Deviation from step b: the manifest lists the release tags older than `VERSION`, and an install fingerprints the template it ships at run time. A release therefore never needs an entry for itself, which stanza's bump commit could not supply. The planned test that the manifest "covers the current template/" would fail whenever dev adds a file no release has shipped, so it became a freshness test: the committed manifest must equal one regenerated from the tags. It fails on dev after each release until `scripts/build_manifest.py` is rerun, and passes on main at the release itself. stanza 1.5.0 has no hook to run the script from, so that test is the wiring; CLAUDE.md and the README name the step.
  - `current` means the file matches the template the install ships. `absent by design` is not implemented: neither of the first two file classes has an optional file. Git state of the Claude files is reported but does not count as drift, since `template/.gitignore` ignores `.claude/` by design.
  - The CLI uses argparse and has no runtime dependencies. Single-repo `--json` prints an object, `--repos-dir --json` an array.
  - The wheel takes `template/` through hatchling `force-include`, which bypasses VCS ignores, so `.claude/` ships. CI checks that the wheel's template is exactly the tracked files.
  - Checks at 43c6349: ruff check and format, pyrefly (strict), and pytest (37 passed) on Python 3.14 and 3.11. Also the shell suite (portability, init behavioral, shellcheck), the wheel-content diff, and `uv tool install .` into a scratch tool dir, with the installed binary run against a real repo.
  - Trial run with `--repos-dir` over a local repos directory: 27 stamped clones in 0.3 s, all stamped 0.11.7 (behind 0.12.0). Four carry a one-off hook script or hook block, and the settings git state is split between tracked and ignored.
- **2026-11-09T15:36:50-08:00** — Implemented: 8 commits ahead of `dev`.

## Handoff

State (2026-11-09): steps a to d are committed and pushed on `feature/012-uv-tool-cli`
(PR #60). Nothing is uncommitted.

Open questions:

1. `init`: port `scripts/init.sh` or call it? Open. Blocks step e only.
2. Before or after plan 011? Answered 2026-11-09: this plan first (see Log).
3. Distribution? Answered 2026-11-09: PyPI, via the gated `publish.yml`.
4. `repotemplates upgrade` as a command? Open. Not needed for a to d.
5. File classes beyond the Claude hooks? Open. Each needs its own comparison
   rule and an `absent by design` case (e.g. `renovate.yml` under Dependabot).

Not verified:

- The new `python` CI job and `publish.yml` have not run on GitHub until this PR's
  checks do. The publish job cannot run until the owner sets up PyPI.

Remaining, in order:

1. The owner adds the PyPI pending publisher (project `repotemplates`, workflow
   `publish.yml`, environment `pypi`), creates the `pypi` environment, and sets
   `PUBLISH_ENABLED`. Waits on the owner.
2. Step f's skill half: the `install-template` preflight reads
   `repotemplates check --json`. Better after the first PyPI release, so the skill
   can install the tool by name.
3. Step e (`init`), after question 1 is answered.
