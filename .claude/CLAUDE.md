# repotemplates

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

## Git hooks in this repo

The root `.pre-commit-config.yaml` carries two planners hooks: `planners-validate`
(pre-commit) and `planners-index` (post-merge). Registration is per-clone, and
`pre-commit` comes from the repo's own `.venv`, not a global install:

```bash
uv sync
uv run pre-commit install --hook-type pre-commit --hook-type post-merge
planners install --check     # both hooks should report `active`
```

A fresh clone has neither hook registered until this runs, and nothing warns about
it — commits and merges simply skip the checks.

`planners` is the one tool expected to be installed globally (`uv tool install
planners`), so the hook entries here call bare `planners`. Everything else a
contributor needs should come from the repo: add dev tooling to the root
`pyproject.toml`'s `dev` group rather than telling people to install it
machine-wide.

## Running uv in this repo

The root `pyproject.toml` is the `repotemplates` package: the typer CLI under
`src/repotemplates/` (`check`, `upgrade`, `stamp`, `init`, `path`, `version`, plus `skill` and
`install` from pkgskills), with `template/` and the two scaffold scripts shipped inside
the wheel as package data. The `install-template` and `install-renovatabot`
skill bodies live in `src/repotemplates/prompts/`, not `.claude/skills/`; a body
names the template as `{cli} path template`, never a checkout path, because it
is printed from an installed release. `test-init` stays in `.claude/skills/`,
since it tests this checkout. The version is `VERSION` alone: hatchling reads it
(`[tool.hatch.version]`), and stanza bumps it, so there is no second version
source. An editable install's metadata keeps the version from its last
`uv sync`; `repotemplates version` in a checkout reads `VERSION` directly.

Run the Python checks after changing `src/`, `tests/`, or `scripts/*.py`:

```bash
uv run ruff check . && uv run ruff format --check .
uv run pyrefly check
uv run pytest
```

The wheel takes `template/` through hatchling's `force-include`, which bypasses
VCS ignores (it must: `template/.gitignore` ignores `.claude/`). It also ships
any stray untracked file under `template/`, such as a `template/uv.lock` or
`template/.venv`, so build releases from a clean tree; CI does, and checks that
the wheel's template is exactly the tracked files.

### Release manifest

`src/repotemplates/data/manifest.json` records the digest of every
template-owned file at every release tag, so `check` can name the release a
consumer's copy matches. It lists the tags older than `VERSION`: an install
fingerprints the template it ships at run time, so a release never needs an
entry for itself, and `main`'s CI passes once the release is tagged.

After each release, once stanza has pushed the tag, regenerate it on `dev` and
commit:

```bash
git fetch --tags
uv run python scripts/build_manifest.py
```

`tests/test_manifest.py` fails while the manifest lacks a tag older than
`VERSION`, so after stanza's post-release bump a skipped
regeneration turns `dev`'s CI red until it is done, and stanza will not bump a
red `dev`.

The root `.python-version` keeps the lock stable across machines whose default
Python differs. Change the pin and `uv.lock` together.

The scaffolding scripts have a shell suite, which CI runs on Linux and
macOS alongside `shellcheck`. Run it after changing `scripts/` or `template/`:

```bash
/bin/bash tests/portability.test.sh
/bin/bash tests/init.test.sh
git ls-files -co --exclude-standard -- '*.sh' | xargs uv run shellcheck
```

The behavioral test scaffolds from this checkout's HEAD, so commit first — it
refuses to run over uncommitted changes to `scripts/`, `template/`, or `VERSION`.
It runs the real `init.sh`, so it needs `rsync` on `PATH`.

`template/` **is** a real, resolvable uv project of its own, and uv discovers a
project by walking up from the working directory to the nearest
`pyproject.toml`. So any uv command run from inside `template/` (`export`,
`sync`, `run`, `lock`) resolves against the template, not the root, and writes
`template/uv.lock` as a side effect. Prefer
`uv run --no-project` for one-off Python; when a dependency audit genuinely
needs the resolved set, exporting from `template/` is fine — just delete the
lock afterward. `/template/uv.lock` is gitignored so a stray one cannot be
committed, which matters because `init.sh` rsyncs `template/` into every
new project excluding only `__pycache__`.
