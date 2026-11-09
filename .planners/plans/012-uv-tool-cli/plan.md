---
id: 12
slug: uv-tool-cli
status: draft
branch:
created: 2026-11-09T15:21:39-08:00
concluded:
pr:
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
