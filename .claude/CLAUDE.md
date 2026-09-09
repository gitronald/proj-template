# proj-template

This file provides guidance to [Claude Code](claude.ai/code).

## Template .claude payload

`template/.gitignore` ignores `.claude/` so that generated repos receive the
files on disk but never track them. In this repo the payload files under
`template/.claude/` are tracked anyway — an ignore rule does not untrack what
is already in the index — but it does gate `git add`, which rejects any
pathspec under the ignored directory whether the file is tracked or not. That
makes every write to the payload awkward:

- **Editing** an existing `template/.claude/` file: plain `git add` refuses
  here too, so stage it with `git add -u template/.claude/<file>` — `-u`
  considers only already-tracked files, so the ignore rule does not apply.
  (`git update-index template/.claude/<file>` and `git commit -a` also work.)
- **Adding** a new file under `template/.claude/`: plain `git add` refuses
  (path is ignored). Enter it into the index once with:

  ```bash
  git update-index --add template/.claude/<file>
  ```

  then commit normally; from then on it behaves like any tracked file. Do
  not use `git add -f`, and do not add a `!.claude/...` negation to
  `template/.gitignore` — a negation would make generated repos track the
  file too.
- `git status` never shows untracked files under `template/.claude/`, so a
  created-but-never-indexed file is silently invisible — verify new payload
  files with `git ls-files template/.claude` after adding.
