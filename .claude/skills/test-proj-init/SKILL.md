---
name: test-proj-init
description: End-to-end test of scripts/proj-init.sh — scaffold a dash-named project, verify placeholder substitution, build, CLI, tests, and GitHub repo state, then report. Use whenever the user wants to test proj-init or the scaffold ("test the template", "rerun the proj-init test", "does the scaffold still work?"), after any change to scripts/proj-init.sh or template/ files, or before releasing proj-template. Also covers the cheap local-only placeholder check that creates no GitHub repo.
---

# Test proj-init

Verifies `scripts/proj-init.sh` actually scaffolds a working project. Start with the
automated suite, which CI also runs on Linux and macOS:

```bash
/bin/bash tests/portability.test.sh   # banned GNU-isms / bash 4 syntax
/bin/bash tests/proj-init.test.sh     # real script, --source this checkout, gh/uv/stanza stubbed
```

It covers placeholders, renames, `CLAUDE_PROJECT_DIR`, the hook's executable bit, the
version stamp, license handling, and deps selection, but stubs `uv` and GitHub — so it
does not prove the scaffold *builds*. The two modes below do:

- **local** — scaffold from this checkout with `--source`, then build and test the
  result. No GitHub repo. Use while iterating on placeholder or rename logic.
- **full** — run the real script end to end: clone, scaffold, `uv sync`, pre-commit,
  initial commit, `stanza init` (creates a real **private** GitHub repo), and branch
  pushes. Use after script changes and before releases.

Default to **full** when the user says "test proj-init" without qualification, and say
up front that a private repo will be created (default name: `template-test`).

## Why a dashed test name

Always test with a dash in the name (default `template-test`). Dashes exercise the
`PROJECT__NAME`/`MODULE__NAME` placeholder split — the repo/dist/CLI name keeps the dash while the
module directory becomes `template_test`. A dash-free name passes even if that logic
regresses, so it proves much less.

## Preconditions

- `gh auth status` succeeds (`repo` scope; `delete_repo` only needed to remove an old
  test repo).
- **The script clones the template; it never reads the working tree.** By default it
  clones GitHub, so pass `--branch dev` to test dev and push first
  (`git log origin/<branch>..<branch>` is empty). With `--source <this checkout>` it
  clones the local repo instead, which picks up unpushed commits — but uncommitted
  edits are invisible either way; commit them first.
- Full mode: the target repo name must be free — `gh repo view <owner>/template-test`
  should fail. If a leftover test repo exists, delete it
  (`gh repo delete <owner>/template-test --yes`); when the token lacks `delete_repo`,
  rename it aside instead (`gh repo rename template-test-old -R <owner>/template-test
  --yes`) and tell the user how to finish the deletion (interactive
  `gh auth refresh -h github.com -s delete_repo`, or the GitHub UI).

## Running

Use a fresh directory under the session scratchpad for every attempt (`run1/`,
`run2/`, ...) — the script's `mkdir` guard fails on an existing target, and fresh
directories avoid recursive deletes. stdin is not a tty here, so the interactive deps
prompt silently defaults to dependabot.

Full mode:

```bash
mkdir -p <scratchpad>/runN && cd <scratchpad>/runN
bash <repo>/scripts/proj-init.sh --branch dev template-test
```

Local mode: the full script still ends in `stanza init` and a push, so run it with the
stubs from `tests/proj-init.test.sh` on `PATH` but without the `uv` stub (copy the
`gh`, `stanza`, and `planners` stubs and their env), then in the result run
`uv sync --all-groups`, `uv run template-test`, `uv run pytest`:

```bash
bash <repo>/scripts/proj-init.sh --source <repo> --deps dependabot template-test
```

Running the real script — not a replay of its lines — keeps the test honest when the
script changes.

Also exercise the validation path once:
`bash scripts/proj-init.sh <scratchpad>/Bad.Name` must print an `Error:` line and exit 1
before creating anything.

## Verify

In the scaffolded project (both modes):

- `grep -rn "MODULE__NAME\|PROJECT__NAME" . --exclude-dir=.git --exclude-dir=.venv` finds nothing.
- `pyproject.toml`: `name = "template-test"`; a `license = "<SPDX>"` line inserted
  after `readme`; repository URL ends in `/template-test`; entry point reads
  `template-test = "template_test.cli:app"`; sdist `only-include` lists
  `/template_test`.
- Module dir is `template_test/` and the test file is `tests/test_template_test.py`.
- `uv run template-test` prints `Hello from template-test!` (single-command Typer app —
  no subcommand); `uv run pytest -q` passes, its coverage table lists `template_test/cli.py`
  (not `MODULE__NAME`), and it reports `Required test coverage of 50.0% reached`.

Full mode additionally:

- `LICENSE` carries the license name, author, and current year.
- The initial commit contains no `.claude/` paths while `.claude/{CLAUDE.md,
  settings.json, settings.local.json, hooks/}` exist on disk — the payload ships
  untracked by design.
- Pre-commit hooks (ruff format, ruff, pyrefly, planners) passed during the initial
  commit — check the script output, don't assume.
- Only the chosen deps automation remains: by default `dependabot.yml` present,
  `renovate.json` and `workflows/renovate.yml` absent.
- `gh repo view <owner>/template-test --json visibility` reports `PRIVATE`; branches
  `main` and `dev` both exist; default branch is `main`.

## Cleanup

Report results and stop — leave the test repo for the user to inspect, and say so.
Delete it only when asked (needs `delete_repo` scope, see Preconditions). Scratch
directories expire with the session.
