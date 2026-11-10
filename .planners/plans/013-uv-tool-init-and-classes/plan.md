---
id: 13
slug: uv-tool-init-and-classes
status: active
branch: feature/013-uv-tool-init-and-classes
created: 2026-11-09T16:05:37-08:00
concluded:
pr: https://github.com/gitronald/repotemplates/pull/61
---

# Add init, upgrade, more file classes, and packaged skills to the repotemplates CLI

## Plan

### Goal

Finish the `repotemplates` CLI that plan 012 started. 012 shipped the package,
the per-release manifest, `check` for one repo and for a repos directory, and
`version`. This plan inherits what 012 left open: its step e (`init`), the skill
half of its step f, its open questions 1, 4, and 5, and the PyPI setup.

### Inherited from plan 012

Open questions, keeping 012's numbers so earlier notes still resolve:

1. (012 q1) Does `init` port `scripts/init.sh` to Python, or call the bash
   script it ships? The bash script supports a fresh machine with no uv (curl to
   bash), which the tool cannot replace.
   **Answered 2026-11-09: call the bash script.** There stays one scaffold
   implementation, and the curl-to-bash path keeps working. Two changes follow.
   The wheel has to ship `scripts/init.sh`, because it ships only `template/`
   today. And `init.sh` needs a way to scaffold from a plain directory, since
   `--source` clones a git repo ("only committed changes are cloned") and the
   packaged template is not one. With both in place, `repotemplates init`
   scaffolds the exact release that is installed.
4. (012 q4) Does upgrade become a command (`repotemplates upgrade`, applying the
   mechanical part of the sync matrix), or stay in the `install-template` skill,
   informed by `check`?
   **Answered 2026-11-09: both. Upgrade becomes a command, and the skill moves
   into the package.** (This corrects an earlier same-day entry, which read the
   answer as skill-only.) The work splits along the sync matrix:
   - **`repotemplates upgrade` (step g)** applies the mechanical part. It
     rewrites a template-owned file only when `check` shows the repo's copy
     equals an earlier release (`matches`), or when it differs only in a way
     the class's rule masks. It leaves alone any file that is `one-off`,
     customized, or absent by design, and reports it. It also bumps the stamp.
   - **The `install-template` skill** keeps the judgment calls: merging
     customized files, the verify gate, and the PR. It runs `upgrade` for
     everything else.

   pkgskills ships the skill inside `repotemplates`:
   `repotemplates skill install-template` prints the body from the installed
   release, and `repotemplates install` writes a version-stamped stub where
   Claude Code and Codex read skills. This takes four changes (step e):
   - The CLI moves from argparse to typer, because pkgskills' `register()`
     mounts its commands on a typer app. typer and PyYAML become the package's
     first runtime dependencies.
   - The body reads `template/` as a path in a checkout. Printed from an
     installed package, it needs a command that names the packaged template
     instead (`paths.template_root()` already locates it).
   - `install-renovatabot` moves with it. `test-init` stays repo-local, because
     it tests this checkout.
   - A downstream fleet-upgrade skill that reads `install-template` from the
     release tag can run `uvx repotemplates@<version> skill install-template`
     instead.
5. (012 q5) Which file classes beyond the Claude hooks are template-owned for
   `check`: pre-commit config, CI workflows, `.gitignore`? Each needs its own
   comparison rule, and where repos legitimately diverge an `absent by design`
   status (e.g. `renovate.yml` in a repo on Dependabot).
   **Answered 2026-11-09 from a fleet survey** (27 stamped repos, all on
   0.11.7; counts in [fleet-survey.md](fleet-survey.md)). Most raw drift is
   legitimate, so the order follows the drift a rule can explain, not the raw
   count:
   1. **Pinned files** (`.pre-commit-config.yaml` and the three workflows): one
      rule that masks `rev:` values, action SHAs and their version comments, and
      the `test.yml` Python matrix list, which follows `requires-python`. It
      reports pins separately. Every pin difference found is a repo *ahead* of
      the template, so "newer pin" must not count as drift.
   2. **Ignore files** (`.gitignore`, `.gitattributes`): containment, with local
      additions allowed. Check behaviour with `git check-ignore` on a probe path
      for each template pattern, not by line text. The fleet writes the same
      rule several ways (`.claude`, `.claude/`, `.claude/*`), and a repo that
      tracks `.claude/settings.json` leaves the `.claude/` rule out on purpose.
   3. **Absent by design**: an `omit` list declared in the stamp table, plus one
      inferred case: the Dependabot and Renovate files exclude each other. The
      non-publishing repos have dropped `publish.yml`, and only a declaration
      can tell that from a file lost by accident.
   Not template-owned for `check`: `.claude/CLAUDE.md` (project prose; 25 of 27
   differ), `.python-version` (two repos pin a patch release), and the
   `pyproject.toml` tool tables. Those are uniform where it matters: every repo
   has the same ruff `select` and pyrefly `strict`, and only `target-version`
   varies, following `requires-python`.

Remaining work (letters stay fixed; the run order is in Handoff):

a. **PyPI setup** (waits on the owner): add the PyPI pending publisher (project
   `repotemplates`, workflow `publish.yml`, environment `pypi`), create the
   `pypi` environment, and set `PUBLISH_ENABLED`. Then cut the first release
   that publishes, and confirm it on PyPI.
b. **Skill preflight**: the `install-template` skill's upgrade preflight reads
   `repotemplates check --json` instead of hashing files by hand. Better after
   a, so the skill can install the tool by name (`uvx repotemplates`).
c. **More file classes** (question 5), each with fixture tests, starting with
   whichever class the fleet shows drifting most.
d. **`init`** (012's step e), once question 1 is answered. The curl-to-bash
   path in the README keeps working.
e. **Ship the skills through pkgskills** (question 4): port the CLI to typer,
   declare a pkgskills `Host` with `install-template` and `install-renovatabot`,
   register the `pkgskills.hosts` entry point, and add the command that names
   the packaged template. Then make the skill bodies use it instead of
   checkout paths. Do this before b, so the preflight is written once, in the
   packaged body.
f. **Template pins lag the fleet**: Dependabot has moved consumers to newer
   `setup-uv` and `ruff-pre-commit` pins than `template/` ships, because the
   root `dependabot.yml` watches only `/`. Add the template's directories, so
   a new scaffold starts on current pins.
g. **`repotemplates upgrade`** (question 4): write the files `check` marks safe
   to replace (`matches`, or masked-equal) from the packaged template, report
   what it skipped and why, and bump the stamp. Add `--dry-run`, which prints
   the plan without writing. A class becomes upgradeable only once c has given
   it a comparison rule; until then the command covers the Claude hooks alone.
   The skill's sync matrix then calls `upgrade` for the mechanical rows.

Not verified at 012's close, and checked here:

- `publish.yml` has never run on GitHub; step a is its first run.

### Out of scope

- Plan 011 (multiple templates). When it lands, it changes
  `paths.template_root()` and teaches `read_stamp` the stamp's `template` key;
  that work belongs to 011.

## Log

- **2026-11-09T18:36:16-08:00** — Activated.
  - Branch: `feature/013-uv-tool-init-and-classes`
  - Base: `dev` at `7b679da`
  - Worktree: `.worktrees/013-uv-tool-init-and-classes`
  - PR: pending
- **2026-11-09T18:41:25-08:00** — PR opened: https://github.com/gitronald/repotemplates/pull/61
- **2026-11-09T18:41:34-08:00** — Step e done (commit 70f2f65). Question 6 answered: global by default, local too (`modes=("global", "local")`).
  - The CLI is typer now; pkgskills mounts `skill` and `install`. typer and pkgskills are the runtime dependencies (PyYAML comes with pkgskills). typer 0.29 vendors click, so there is no separate click dependency.
  - `install-template` and `install-renovatabot` moved from `.claude/skills/` to `src/repotemplates/prompts/`, declared in `src/repotemplates/host.py` and registered under `pkgskills.hosts`. `test-init` stays.
  - `repotemplates path template|scripts` names the shipped directories. The wheel ships `scripts/init.sh` and `scripts/renovatabot-enroll.sh`, which step d needs too. CI checks the wheel carries both scripts and both skill bodies.
  - The bodies read `{cli} path template` and `{cli} path scripts`; the Renovate guide is linked by URL. Mode 1 of `install-template` still names `scripts/init.sh` until d lands.
  - Checked: ruff, pyrefly, and pytest (51 passed), plus a wheel built and run with `uv run --isolated --with <wheel>`, where `path scripts` resolved inside site-packages.
- **2026-11-09T18:49:37-08:00** — Step d done (commits for `init.sh --template-dir` and `repotemplates init`). Question 1's answer stands: `init` calls the shipped bash script.
  - `init.sh` gains `--template-dir <dir>`, which copies a plain template directory instead of cloning, and `--template-version <v>` (default: a `VERSION` file beside the directory). Neither combines with `--source` or `--branch`, and the script rejects a directory with no `MODULE__NAME/`.
  - `repotemplates init <path> [--license] [--deps]` runs the shipped `init.sh` on the shipped template with `--template-version` set to the installed release. `install-template`'s Mode 1 now runs `{cli} init`; a checkout or fork still scaffolds through its own `scripts/init.sh --source`.
  - Checked: the shell suite passes, including 11 new checks. One scaffold from a `git archive` of HEAD's `template/` matches the clone scaffold file for file once the project name is mapped (the stamp aside). The `same_tree` comparison was not mutation-tested. pytest (54 passed) covers the argv `init` builds. A wheel run of `repotemplates init`, with gh, uv, stanza, and planners stubbed, scaffolded a repo stamped with the wheel's version, with the Stop hook still executable.
- **2026-11-09T18:56:12-08:00** — Step c done, in the order question 5 gave.
  - Pinned (`.pre-commit-config.yaml`, the `test`, `publish`, and `renovate` workflows): one rule masks `rev:` values, action refs and their version comments, and a `python-version` matrix list. The manifest records the masked digest, so a pin bump alone makes no new release copy. Pins get their own verdict (`same`, `ahead`, `behind`, `mixed`, `differs`). `ahead` is not drift; `behind`, `mixed`, and `differs` keep a repo from `current`.
  - Config (`dependabot.yml`, `renovate.json`): exact content, in the manifest.
  - Ignore (`.gitignore`, `.gitattributes`): containment by behaviour. Each template rule gets a probe path, which `git check-ignore --no-index` and `git check-attr` answer with the user's excludes and attributes files switched off. A rule that does not hold is waived when the repo tracks a path it would ignore. That came out of the first fleet run: 9 of 12 gaps were `.claude/` in repos that track `.claude/`. Ignore files are compared against the shipped template only, not the manifest.
  - Absent by design: `omit` in the stamp table, plus the inferred Dependabot/Renovate exclusion.
  - A read-only `check --repos-dir` over the local fleet (27 stamped repos) now shows the survey's matrix narrowing as `current`, the newer `setup-uv` and ruff pins as `pins ahead`, and every Renovate or Dependabot counterpart as `omitted`. What remains: 11 one-off `test.yml` (extra setup steps), 3 one-off hook entries, 6 missing `publish.yml` (non-publishing repos to declare in `omit`), and 2 real ignore gaps (`.coverage`, `.coverage.*` in one repo).
  - Checked: ruff, pyrefly, and pytest (75 passed); the manifest was regenerated from the tags.

## Handoff

State on 2026-11-09: still a draft, with no branch and no code. Questions 1, 4,
and 5 are answered above. The fleet survey behind question 5 is in
[fleet-survey.md](fleet-survey.md).

Open questions (numbering continues from 012's):

6. Where should `repotemplates install` put the skill stubs by default? A global
   install (`~/.claude/skills/`) fits a skill that is run against other repos.
   A local install in this repo replaces the tracked `.claude/skills/` copies.
   pkgskills lets a host declare either mode, or both.

Order of the remaining work, and what each step waits on:

1. a (PyPI setup): waits on the owner.
2. e (pkgskills): can start now. It does not need a.
3. b (skill preflight): after e, and better after a.
4. c (file classes), in the order question 5 gives: pinned files, then ignore
   files, then absent by design.
5. g (`upgrade`): can start after e with the hooks only, and grows a class at a
   time as c lands. The skill's switch to calling it follows.
6. d (`init`): independent of c and g.
7. f (template pins): small and independent, and can land at any time.

The plan is now about 160 lines across seven steps. If g or c grows large,
split them into nested subplans then.

Not verified: the survey's comparisons are line-based. Which `.gitignore`
differences are only pattern spellings is a reading of the lines, not a
`git check-ignore` result.
