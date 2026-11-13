---
id: 15
slug: stamp-first-adoption-ignored-claude
status: draft
branch:
created: 2026-11-13T14:36:38-08:00
concluded:
pr:
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
