---
id: 14
slug: stamp-without-force
status: active
branch: feature/014-stamp-without-force
created: 2026-11-13T10:32:22-08:00
concluded:
pr: https://github.com/gitronald/repotemplates/pull/70
---

# Let stamp finish a fleet upgrade without --force

## Plan

### Goal

A fleet pass with 0.15.0 had to run `repotemplates stamp --force` on most of the
repos it upgraded, even when the upgrade was finished. Each `--force` came from
one of the four gaps below, not from a file left behind. When `--force` is
routine, it no longer tells a finished upgrade from an unfinished one. Close the
four gaps so that `stamp` refuses only when a file really is behind.

Each gap was re-checked against 0.15.0 (2026-11-13) by reading `check.py` and
`upgrade.py`, and gaps 3 and 4 also by calling `read_stamp` and `set_stamp` on a
scratch `pyproject.toml`.

### Gaps

1. **An ignored `.claude/` reads `missing` in a linked worktree.** A repo that
   gitignores `.claude/` keeps the Stop hook and `settings.json` in its main
   checkout only. `git worktree add` copies tracked files, so the worktree
   where the upgrade runs has neither, and `check_repo` reports both `missing`.
   `stamp` then refuses, although the main checkout is current.
   - Approach: when the repo is a linked worktree (`git rev-parse
     --git-common-dir` differs from `--git-dir`) and an absent template file is
     ignored there, read it from the main worktree, and report where it was read
     in the row. `git check-ignore` answers for an absent path, so the ignore
     test still works.
   - Alternative, if reading another tree is unwelcome: a status of its own
     (`elsewhere`) that `stamp` accepts and `upgrade` leaves alone.
2. **No record for a kept customization.** `omit` records a template file the
   repo leaves out, but nothing records one the repo keeps in its own form: a
   Stop hook with an extra step, an adapted `test.yml`, a pre-commit config with
   an added hook, a `dependabot.yml` covering a second lockfile. `check` reads
   each `one-off`, and `stamp` refuses. One repo needed `--force` for three such
   files.
   - Approach: a `keep` list in the stamp table, beside `omit`. A listed file
     that matches no release reads `kept` instead of `one-off`, counts as
     current for `stamp`, and `upgrade` skips it with the reason "kept".
   - A kept file still needs a way to see when the template moves on. Record the
     release it was last reviewed against (for example `keep = {".github/
     workflows/test.yml" = "0.15.0"}`), and have `check` flag it once the
     template's copy changes after that release. Decide between that and a
     plain list during implementation.
   - The install-template skill names the list where it says to keep a
     customization.
3. **`check` ignores `omit` on a never-stamped repo.** A table that holds
   `omit` but no `version` reads `unreadable`, and `read_stamp` drops the
   `omit` it found (`StampReport(version=None, ..., status='unreadable',
   omit=())`). The first stamp of a repo that leaves a file out therefore always
   needs `--force`.
   - Approach: a table with a valid `omit` and no `version` reads as `missing`
     (not stamped yet), carrying its `omit`. `unreadable` stays for a table
     that is not a table, or an `omit` that is not a list of paths.
4. **`stamp` keeps a hand-written table without the comment line.** On a repo
   with no table, `set_stamp` adds the comment line above it. On a repo whose
   table someone wrote first to hold `omit` (the usual order on a first stamp,
   given gap 3), it adds `version` and leaves the table with no comment line
   above it.
   - Approach: when `set_stamp` finds the table with no template comment above
     it, insert `STAMP_COMMENT`. Comment lines the repo wrote itself stay where
     they are, as `_comment_start` already provides.

### Order

3 and 4 first: they are small, and both are on the first-stamp path. Then 1,
then 2, which adds a key to the stamp table and needs the skill and the docs
updated with it. Each gets a test in `tests/test_check.py` or
`tests/test_upgrade.py` that reproduces the refusal first.

### Done when

- On a scratch repo in each of the four shapes, `stamp` succeeds without
  `--force` once the upgrade is finished, and still refuses with a file
  genuinely behind.
- The install-template skill, `README.md`, and the CHANGELOG describe `keep` and
  the worktree behaviour.

### Out of scope

- Changing what `upgrade` writes for files it already handles.

## Log

- **2026-11-13T11:10:06-08:00** — Activated.
  - Branch: `feature/014-stamp-without-force`
  - Base: `dev` at `da133d7`
  - Worktree: `.worktrees/014-stamp-without-force`
  - PR: pending
- **2026-11-13T11:13:05-08:00** — PR opened: https://github.com/gitronald/repotemplates/pull/70
