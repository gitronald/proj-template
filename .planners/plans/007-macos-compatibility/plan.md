---
id: 7
slug: macos-compatibility
status: done
branch: feature/macos-compatibility
created: 2026-09-09T23:12:15-07:00
concluded: 2026-09-10T17:08:42-07:00
pr: https://github.com/gitronald/proj-template/pull/40
---

# Make the scaffolding scripts run on macOS

## Plan

### Why

`scripts/proj-init.sh` depends on GNU coreutils behavior and bash 4 syntax. On a
stock macOS box — bash 3.2 as `/bin/bash`, BSD `sed`, BSD `grep` — it fails, and
several of the failures are silent rather than loud: a BSD `sed` that does not
understand `\b` treats it as a literal `b`, so the placeholder pass matches
nothing and the scaffolded repo ships with `PROJECT` and `MODULE` still in it.

This was latent before 0.9.2 and is now load-bearing: the fixes in that cycle
added `${LICENSE,,}` (bash 4), `sed -i` (GNU spelling), and `\b` word boundaries
(GNU regex) to close real bugs. Those were the right fixes on Linux; they
deepened the macOS gap. Closing it now keeps the template usable by anyone not on
Linux, which for a *template* is most of its potential audience.

The Stop hook shipped in `template/.claude/hooks/lint-typecheck.sh` is already
portable (`set -u`, no GNU-isms, no bash 4 syntax) and needs no work — worth
stating so a later reader does not re-audit it.

### Inventory

Everything below is in `scripts/proj-init.sh`. `scripts/renovatabot-enroll.sh`
is clean, though it hardcodes `#!/bin/bash` and should move to
`#!/usr/bin/env bash` for consistency.

| Construct | Requires | macOS failure mode |
| --- | --- | --- |
| `${LICENSE,,}` | bash 4.0 | Syntax error under bash 3.2 — loud, aborts immediately |
| `sed -i "s/.../.../"` | GNU sed | BSD `sed -i` consumes the next argument as a backup suffix; the expression is then read as a filename |
| `\bMODULE\b`, `\bPROJECT\b` in `sed` | GNU sed | **Silent.** `\b` is a literal `b`, nothing matches, placeholders survive into the scaffolded repo |
| `\b...\b` in `grep -rlE` | GNU grep | **Silent.** Same — the file list comes back empty and the substitution loop is skipped entirely |
| `<<< "$placeholder_files"` | bash 3.0+ | None — herestrings work in 3.2 |
| `set -o pipefail`, `set -u` | bash 3.0+ | None |
| `find ... -depth`, `mktemp -d`, `basename`, `dirname`, `tr`, `date +%Y` | POSIX | None |

The two silent rows are the dangerous ones: the script exits 0 and prints
"Done", having produced a broken repo.

### Portability conventions to adopt

These are settled practice in bash tooling that already runs reliably on both
platforms. Adopt them wholesale rather than rediscovering them per call site —
the point is that a reviewer can check conformance by grepping for the banned
construct, instead of reasoning about each regex.

| Rule | Instead of |
| --- | --- |
| Never use `sed -i`. Write to a temp file, then copy back | in-place editing |
| Use `sed -E` for extended regex | `sed -r` (GNU-only spelling) |
| Use POSIX classes: `[[:space:]]`, `[[:digit:]]`, `[[:alpha:]]` | `\s`, `\d`, `\w`, `\b` |
| Spell out repetition: `(\.[0-9]+)?` | `{0,1}` / `{n,m}` intervals, which old BSD awk rejects |
| No bash 4 syntax: no `${v,,}`, `${v^^}`, `mapfile`, `readarray`, `declare -A` | any of those |
| Resolve script dir via `${BASH_SOURCE[0]:-$0}` | bare `$0` |
| Guard the interpreter at entry: `[ -z "$BASH_VERSION" ] && { echo "Error: requires bash" >&2; exit 1; }` | assuming bash |
| Strip `\r` when reading files that may have CRLF endings: `tr -d '\r'` | assuming LF |

### Approach

Three workstreams, in order. The first two are independent; the third verifies
both and keeps them from regressing.

**1. Remove the bash 4 dependency.**

Replace `${LICENSE,,}` with `tr '[:upper:]' '[:lower:]'`. That is the only bash 4
construct in the script today; `${NAME//-/_}` and `[[ =~ ]]` both work in 3.2.
Keep `#!/usr/bin/env bash` so a Homebrew bash on `PATH` is still preferred, but
stop *requiring* it, and add the `BASH_VERSION` guard so running under `sh`
fails with a sentence rather than a syntax error.

**2. Remove the GNU sed/grep dependency — by deleting the need for word
boundaries, not by porting them.**

`[[:<:]]`/`[[:>:]]` is the BSD spelling of `\b`, but branching on the platform
means two regex dialects to keep correct forever, and the failure mode of getting
it wrong is the silent one. Remove the requirement instead: rename the
placeholders so they cannot collide with real identifiers.

- `PROJECT` -> `__PROJECT__`, `MODULE` -> `__MODULE__` throughout `template/`,
  and in the `find -name` pattern for path renames.
- The substitution becomes a plain literal match — no `\b`, no dialect
  difference, and structurally immune to the `CLAUDE_PROJECT_DIR` class of bug
  that 0.9.2 fixed with word boundaries. A placeholder that cannot appear inside
  another token needs no boundary assertion, which is the more robust fix on
  either platform.
- Replace `sed -i` with the portable in-place idiom. The usual spelling is
  `sed ... "$f" > "$f.tmp" && mv "$f.tmp" "$f"`, but `mv` installs a fresh inode
  with default permissions — that is exactly the bug 0.9.2 fixed by adopting
  `sed -i`, and it would strip the executable bit off
  `.claude/hooks/lint-typecheck.sh` again. Copy the content back instead, which
  truncates and rewrites the existing inode:

  ```sh
  sed "s/__MODULE__/${MOD_NAME}/g; s/__PROJECT__/${NAME}/g" "$f" > "$f.tmp" \
      && cat "$f.tmp" > "$f" && rm -f "$f.tmp"
  ```

  Comment the `cat` — the obvious "simplification" back to `mv` reintroduces the
  mode-loss bug, and this is the one place where the portable idiom and the
  correct idiom differ.

The `find -name '*MODULE*'` pattern and the `mv` basename rewrite must move to
the new spelling in the same commit, or the path renames silently stop matching.

**3. Verify on an actual macOS runner.**

The repo has no CI at all today, which is why both silent failures went
unnoticed. Two layers:

*Behavioral tests.* Follow the fixture pattern that works for shell tooling:
`mktemp -d`, build a throwaway repo with `git init`, run the real entry point
against it, assert, clean up. `proj-init.sh` currently blocks this by cloning
`REPO_URL` over the network and then calling `gh` and pushing — so make the
template source injectable (a `--template-dir` flag, or an env override for
`REPO_URL`) and let the tests point it at the local checkout. Assert:

  - no `__PROJECT__`/`__MODULE__` survives anywhere in the output tree;
  - `CLAUDE_PROJECT_DIR` is intact in `.claude/settings.json` and
    `.claude/hooks/lint-typecheck.sh`;
  - `.claude/hooks/lint-typecheck.sh` is still executable;
  - the renamed package dir and test file exist;
  - `[tool.proj-template]` carries the template's `VERSION`.

Those five cover every bug found across 0.9.0-0.9.2 plus both silent macOS
failures — the suite is worth building for the regression value alone, macOS
aside.

*A grep-based portability guard.* One test that fails if any banned construct
from the table above appears in `scripts/*.sh` or `template/**/*.sh`. Cheap,
runs anywhere, and catches a reintroduced `sed -i` on Linux where it would
otherwise pass.

Then add `.github/workflows/test.yml` with a matrix of `ubuntu-latest` and
`macos-latest` running both layers, plus `shellcheck` over the same files.
shellcheck is not installed in the current dev environment, so these scripts have
never been linted; it flags unquoted expansions and pipeline-masked exit statuses
directly — both of which were live bugs here in 0.9.1 and 0.9.2.

### Out of scope

- Porting `renovatabot-enroll.sh` beyond its shebang — it is already portable.
- Supporting `sh`/`dash`. The target is bash 3.2+, not POSIX sh.
- Windows. `proj-init.sh` assumes a Unix filesystem and `rsync`.
- Making the template's *generated* projects macOS-friendly. They already are —
  `uv`, `ruff`, and `pyrefly` all ship macOS builds, and the hook is portable.

### Risks

- **The placeholder rename touches every file in `template/`.** It also
  invalidates assumptions in the `install-template` skill, whose sync matrix
  diffs a target's files against `template/`: a repo scaffolded before this
  change carries the bare spelling and must not have `__PROJECT__` pasted into
  it. Cover that in the same PR.
- **A macOS runner will surface unrelated failures first.** The `rsync` on macOS
  is old, and recent versions ship `openrsync` instead. Expect the first CI run
  to fail for reasons outside this plan; triage rather than widening scope.
- **Injecting the template source is a real behavior change**, not just a test
  seam — it becomes a supported way to scaffold from a fork. Decide whether that
  is desirable before shipping it, since it is hard to withdraw later.
- **The network and `gh` paths stay untested.** Accepted gap; covering them needs
  a fixture GitHub org, which is a larger piece of work.

### Acceptance

- `bash scripts/proj-init.sh --help` and `--version` run clean under bash 3.2.
- The behavioral suite and the portability guard pass on both `ubuntu-latest`
  and `macos-latest`.
- A repo scaffolded on macOS is byte-identical to one scaffolded on Linux, given
  the same name and template version.

## Log

### 2026-09-10 — implementation

Activated on `dev`; worked in `.worktrees/macos-compatibility`, draft PR #40.

**Reproduced on a stock Mac first** (bash 3.2.57, BSD sed/grep, `openrsync`):
`${LICENSE,,}` aborts with `bad substitution`, and BSD `sed` leaves
`s/\bPROJECT\b/.../` unmatched — placeholder survives, exit 0. One correction to
the inventory table: macOS `grep -E` *does* honor `\b`, so the file list is
found and only the `sed` pass silently no-ops. Same broken output, different row.

**Deviations from the spec, both decided with the user:**

- **Spelling is `PROJECT__NAME` / `MODULE__NAME`, not `__PROJECT__` /
  `__MODULE__`.** `template/pyproject.toml` has `name = "PROJECT"`, and uv
  rejects `__PROJECT__` ("Names must start and end with a letter or digit"),
  which would stop `template/` resolving as a uv project. The double-underscore
  infix keeps the property the plan wanted — no collision with
  `CLAUDE_PROJECT_DIR` or any identifier, so a plain literal match — while
  staying a valid package name and Python identifier. Used for both
  placeholders for symmetry. The script comment warns against "tidying" it to
  `__PROJECT__`.
- **Template-source seam is `--source <repo>`, and it clones.** A documented
  flag (the user's choice over an env var). Rather than copying a checkout's
  `template/` — which would also copy gitignored strays like `template/uv.lock`
  or `.venv` — it swaps the clone URL (`file://` for a local path so `--depth`
  is honored), so the output is exactly what a GitHub scaffold produces. That
  made it combinable with `--branch` instead of exclusive; `--branch` now
  defaults to the source's default branch (still `main` on GitHub). `--`
  precedes the URL so a `-`-prefixed value is not read as a git option.
  Trade-off: uncommitted edits are not scaffolded.

**Portable in-place edit** is `sed > tmp; cat tmp > f; rm tmp`, commented
against the `mv` "simplification". With the new spelling the hook file no longer
contains a placeholder at all, but the idiom still guards any future executable.
`find -name ... -depth` reordered to `find -depth -name ...` (GNU warns on the
former).

**Tests** live in `tests/` as plain bash (no bats dependency).
`proj-init.test.sh` runs the real script under `/bin/bash` with `gh`, `uv`,
`stanza`, and `planners` stubbed on `PATH` (the `stanza` stub points `origin` at
a local bare repo so the push succeeds) and git isolated via
`GIT_CONFIG_GLOBAL`. It asserts the plan's five checks plus license folding and
insertion, deps selection, the initial commit, and the validation path.
`portability.test.sh` greps comment-stripped lines of every `*.sh` for the banned
constructs, and each rule self-checks against a sample so a rotted regex fails
loudly. Both pass locally on macOS; `openrsync` caused no trouble.

**shellcheck** (first-ever run, via `shellcheck-py`): `proj-init.sh` clean. It
flagged SC1090 on the runtime-chosen `.env` source in `renovatabot-enroll.sh`
(directive added — the only change there beyond the shebang) and SC2016 on the
tests' intentionally literal `$` strings (suppressed at those sites).

**CI**: `.github/workflows/test.yml` — shellcheck on ubuntu; guard and
behavioral suite on `ubuntu-latest` and `macos-latest` under `/bin/bash`; each
uploads a checksum-plus-exec-bit manifest and an `identical` job diffs them for
the byte-identical acceptance criterion. Actions SHA-pinned to the template's
versions.

Docs: README, CHANGELOG `[Unreleased]`, and both skills updated — including the
plan's install-template risk, now an explicit "placeholders are never copied"
note covering both old and new spellings.

### 2026-09-10 — review follow-up

`/code-review` on PR #40 (posted as a PR comment) returned 15 verified findings.
Fixed the 13 this PR introduced, each paired with a test, and proved every new
test by mutation: reverting its fix in a scratch clone makes the suite fail.

- **Regression: `template/.claude/CLAUDE.md` still said `MODULE/`.** The rename
  missed it (gitignore-aware search skips `template/.claude/`), and the literal
  `MODULE__NAME` match never selects it, so every scaffold shipped the bare
  placeholder. CI stayed green because the assertions looked only for the new
  spellings. Fixed the file. The content check now also matches bare
  `PROJECT`/`MODULE`, word-bounded with `grep -w` so `CLAUDE_PROJECT_DIR` is not a
  hit, and fails on grep exit 2. The path check matches both spellings too.
- **Template check before `mkdir`.** A clone with no `template/MODULE__NAME/`
  errors before anything is created. That covers a repo that is not a
  proj-template, an "empty" clone of a mirror whose HEAD names a missing branch,
  and a pre-rename release. The script also prints the commit it cloned.
- **`--source` clones with `--no-local` on the raw path** instead of building a
  `file://` URL. git percent-decoded that URL (a `%41` in the path named another
  directory), and the `cd` that built it ran without `--`.
- **`set +o noclobber`**, so an exported SHELLOPTS cannot break the cat-back.
- **Empty option values are rejected** (`--branch ""`, `--source ""`, and so on)
  rather than read as "use the default".
- **Tests.** An executable fixture carrying a placeholder: the stock template's
  executables have none, which is why reverting cat-back to `mv` had kept the
  suite green. It is scaffolded under an exported noclobber from a relative
  `fix%41src` path. Also new: a `rejects` helper that asserts the specific
  `Error:` text, a non-template source, and a refusal to run over uncommitted
  `scripts/`, `template/`, or `VERSION` changes, since `--source` clones HEAD
  while the script under test is the working-tree copy.
- **Portability guard.** New rules for GNU BRE escapes (`\|` `\+` `\?` `\<`
  `\>`), `${a[i],,}`, and `sed -E -i`. `ls-files -z` means non-ASCII paths are
  scanned, grep exit 2 fails the check, and each rule takes several self-check
  samples.
- **Docs.** The `--branch` default is now described accurately: a local
  `--source` clones its checked-out branch. The `sh` wording is corrected:
  macOS `/bin/sh` is bash in POSIX mode, and the guard's real ordering
  constraint is `set -o pipefail`. The repo's `.claude/CLAUDE.md` now names the
  shell suite.

Mutations, all killed: the CLAUDE.md placeholder, the `mv` copy-back, the
noclobber reset, the template check, empty `--branch`, and the `file://` URL.
The full suite passes all 33 checks under `/bin/bash` 3.2 locally, and CI is
green on both OSes.

**Conscious no-ops:**

- Deferred because they predate this PR, as follow-up plan candidates:
  - `core.autocrlf=true` produces CRLF template files and a `\r` in the version
    stamp.
  - The no-op `uv` stub means the scaffold's pre-commit hooks never run in the
    suite, and no stub call is asserted.
- A house rule prefers `#!/bin/bash`. Both scripts keep `#!/usr/bin/env bash`,
  as this plan decided, so a Homebrew bash on `PATH` is still preferred.
- Low-severity items cut by the review's cap, not actioned:
  - A project named `tests` nests its package inside `tests/` (predates this
    PR).
  - The `identical` job can flake across New Year, because each leg stamps its
    own LICENSE year.
  - The test files are committed 0644.
  - The script uses two in-place-edit idioms.
  - The two `git clone` lines are near-duplicates.
  - CI has no concurrency group.

## Retrospective

- The one real regression was predicted in outline but not in detail. The
  Risks section warned that the rename touches "every file in `template/`", yet
  the file it missed is under the ignored `template/.claude/`, which every
  gitignore-aware search skips. Any repo-wide rename here should take its
  inventory with `git grep` or `git ls-files`, not `rg`.
- An assertion written against the new spelling can only prove the new
  spelling is gone. A placeholder check has to look for every spelling that
  ever existed. This one stayed green because it shared the implementation's
  blind spot.
- A claim that a test covers X needs a mutation behind it. The executable-bit
  check passed with its fix reverted, because no executable carried a
  placeholder. Reverting each fix in a scratch clone was cheap and settled the
  question for all six.
- The macOS port itself went to plan. `openrsync` and the macOS runner caused
  none of the trouble the Risks section expected, and review found no reason to
  revisit either spec deviation (the `PROJECT__NAME` spelling or `--source`
  cloning).
- `--source` grew more surface than a test seam should: URL handling, HEAD
  semantics, empty values, and validation. Five of the 13 fixed findings were
  about it, which bears out the plan's warning to decide whether the flag was
  desirable before shipping it.
