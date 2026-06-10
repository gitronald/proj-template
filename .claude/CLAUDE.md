# proj-template

This file provides guidance to [Claude Code](claude.ai/code).

## Template .claude payload

`template/.gitignore` ignores `.claude/` so that generated repos receive the
files on disk but never track them. In this repo the payload files under
`template/.claude/` are tracked anyway — gitignore only affects untracked
files — which makes maintenance asymmetric:

- **Editing** an existing `template/.claude/` file: normal `git add` and
  commit.
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
