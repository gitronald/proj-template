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

## Running uv in this repo

The repo root has **no `pyproject.toml`** — proj-template ships a scaffold and
shell scripts, not a Python package of its own. So there is no test, lint, or
type-check suite to run here, and `uv run <anything>` at the root correctly
fails with `No pyproject.toml found in current directory or any parent`. That
is expected; it is not a broken environment to repair.

`template/` **is** a real, resolvable uv project, and uv discovers a project by
walking up from the working directory. The two facts combine into a trap: the
root failure invites a `cd template/`, and any uv command run there (`export`,
`sync`, `run`, `lock`) writes `template/uv.lock` as a side effect. Prefer
`uv run --no-project` for one-off Python; when a dependency audit genuinely
needs the resolved set, exporting from `template/` is fine — just delete the
lock afterward. `/template/uv.lock` is gitignored so a stray one cannot be
committed, which matters because `proj-init.sh` rsyncs `template/` into every
new project excluding only `__pycache__`.
