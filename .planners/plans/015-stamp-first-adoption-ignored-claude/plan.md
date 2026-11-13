---
id: 15
slug: stamp-first-adoption-ignored-claude
status: implemented
branch: feature/015-stamp-first-adoption-ignored-claude
created: 2026-11-13T14:36:38-08:00
concluded:
pr: https://github.com/gitronald/repotemplates/pull/72
---

# Let a first stamp through when an ignored .claude/ exists in no checkout

## Plan

### Problem

Plan 014 let `check` read a linked worktree's gitignored `.claude/` files from
the main worktree (`_root_for` in `check.py`), so a finished upgrade stamps
without `--force`. That covers a repo that already had the Stop hook and
`settings.json` in its main checkout. It does not cover a repo taking the
template for the first time: the main checkout has no copy either, and the
install-template skill forbids writing one there before the upgrade's PR
merges. `check` reads the hook and the `settings.json` hooks `missing`, and
`stamp` refuses. Seen with 0.16.0 on 2026-11-13: a repo's first adoption
needed `stamp --force` for these two rows alone.

The files are ignored, so the PR can never carry them; they are written into
each checkout after the merge. A stamp that waits for them waits on something
the branch cannot hold.

### Options

1. **A status of its own.** When a template file is missing from the repo and
   from the main worktree, and the repo ignores its path, read it `local`
   (ignored, not in any checkout) rather than `missing`. `stamp` accepts it;
   `check` lists it so the post-merge step is not forgotten; `upgrade` still
   offers to write it into the checkout it runs in.
2. **Write the files into the worktree.** The skill writes the ignored files
   into the worktree during the upgrade, where `check` then reads them
   `current`. No code change, but the copies vanish with the worktree and
   the main checkout still needs them after the merge, so the step happens
   twice.
3. **Leave it, and document `--force`** for this one case in the skill.

Option 1 is the proposal: it keeps `--force` meaning "a file really is
behind", which was plan 014's goal, and it says what is left to do.

### Approach (option 1)

- In `check_repo`, for a shipped file with no copy in the repo or the main
  worktree, test `git check-ignore` on its path. Ignored reads `local`.
  `settings.json`'s hook entries follow the file's path.
- `FileReport.current` treats `local` as current for `stamp` only; the
  rendered table and `--json` show it with a note ("ignored; write it in each
  checkout after the merge").
- The install-template skill's post-merge step names the `local` rows as the
  files to write.

### Done when

- A scratch repo that ignores `.claude/`, with no copy in any checkout,
  finished in a linked worktree: `stamp` succeeds without `--force`, and
  `check` lists the two rows as `local`.
- The same repo with a stale hook in the main checkout still refuses.
- Tests in `tests/test_check.py` and `tests/test_upgrade.py`, failing first
  on 0.16.0; the README, CHANGELOG, and skill describe `local`.

### Out of scope

- A repo that tracks `.claude/`: its files travel in the PR and need nothing
  new.

## Log

- **2026-11-13T14:44:43-08:00** — Activated.
  - Branch: `feature/015-stamp-first-adoption-ignored-claude`
  - Base: `dev` at `c319762`
  - Worktree: `.worktrees/015-stamp-first-adoption-ignored-claude`
  - PR: pending
- **2026-11-13T14:52:46-08:00** — Drafted by Codex (gpt-6-astra) from a brief, reviewed and verified in the main session. Pass 1: check_repo reads an ignored shipped file absent from both checkouts as local (main checkout too, omitted still wins); option b, plan_stamp accepts local while FileReport.current stays false so check keeps exiting 1 until the post-merge write; upgrade now writes a local file's template copy, which it never did for missing (the plan had assumed it did); README, CHANGELOG, and the install-template skill updated. Review found the new hook created 0644 while settings.json runs it by path; pass 2 copies the template's mode onto newly created files, with a test that failed first. A guard for a template path that does not exist added by hand. 179 tests, portability, init, and shellcheck pass. Scratch first-adoption probe (a fresh clone, no .claude in any checkout, linked worktree): 0.16.0 refuses the stamp; this branch reads both rows local, stamps without --force, and upgrade writes the hook 755 and settings.json 644.
- **2026-11-13T14:52:52-08:00** — PR opened: https://github.com/gitronald/repotemplates/pull/72
- **2026-11-13T14:55:06-08:00** — Implemented: 4 commits ahead of `dev`.
- **2026-11-13T15:11:10-08:00** — Review gate run by Codex (gpt-6-astra) at the owner's request, verified in the main session; 185 tests, portability, and shellcheck pass.
  - Review follow-up: raised three. (1) A dangling symlink or a non-directory in the way of an ignored file read local, so stamp passed and upgrade could follow the link or crash: actioned, local now requires the path to be creatable in both checkouts, four regression cases. (2) An ignored, absent pre-commit config written as local took the template's ruff rev without the relock: actioned, the ruff sync now reads the planned content, two regression cases. (3) pyrefly's always-False warning in an existing ruff test predates the branch: conscious no-op.
