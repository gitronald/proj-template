---
name: test-proj-init
description: End-to-end test of scripts/proj-init.sh — scaffold a dash-named project, verify placeholder substitution, build, CLI, tests, and GitHub repo state, then report. Use whenever the user wants to test proj-init or the scaffold ("test the template", "rerun the proj-init test", "does the scaffold still work?"), after any change to scripts/proj-init.sh or template/ files, or before releasing proj-template. Also covers the cheap local-only placeholder check that creates no GitHub repo.
---

# Test proj-init

Verifies `scripts/proj-init.sh` actually scaffolds a working project. Two modes:

- **local** — replay only the placeholder/rename logic against the working tree's
  `template/`, then build and test the result. No network, no GitHub repo. Use while
  iterating on placeholder or rename logic.
- **full** — run the real script end to end: clone, scaffold, `uv sync`, pre-commit,
  initial commit, `stanza init` (creates a real **private** GitHub repo), and branch
  pushes. Use after script changes and before releases.

Default to **full** when the user says "test proj-init" without qualification, and say
up front that a private repo will be created (default name: `template-test`).

## Why a dashed test name

Always test with a dash in the name (default `template-test`). Dashes exercise the
`PROJECT`/`MODULE` placeholder split — the repo/dist/CLI name keeps the dash while the
module directory becomes `template_test`. A dash-free name passes even if that logic
regresses, so it proves much less.

## Preconditions

- `gh auth status` succeeds (`repo` scope; `delete_repo` only needed to remove an old
  test repo).
- **The script clones the template from GitHub, not the local checkout.** Run
  `git fetch` and confirm the branch under test is pushed
  (`git log origin/<branch>..<branch>` is empty). Pass `--branch dev` to test dev —
  unpushed local edits are invisible to a full run; commit and push them first.
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

Local mode: rsync `template/` to a fresh scratch dir named `template-test`, then replay
the rename and substitution stages *as currently written in `scripts/proj-init.sh`*
(the `find … '*MODULE*'` rename loop and the `sed "s/MODULE/…; s/PROJECT/…"`
replacement, with `NAME=template-test`, `MOD_NAME=template_test`), then
`uv sync --all-groups`, `uv run template-test`, `uv run pytest`. Copy the lines from
the script rather than from this file so the test stays honest when the script changes.

Also exercise the validation path once:
`bash scripts/proj-init.sh <scratchpad>/Bad.Name` must print an `Error:` line and exit 1
before creating anything.

## Verify

In the scaffolded project (both modes):

- `grep -rn "MODULE\|PROJECT" . --exclude-dir=.git --exclude-dir=.venv` finds nothing.
- `pyproject.toml`: `name = "template-test"`; a `license = "<SPDX>"` line inserted
  after `readme`; repository URL ends in `/template-test`; entry point reads
  `template-test = "template_test.cli:app"`; sdist `only-include` lists
  `/template_test`.
- Module dir is `template_test/` and the test file is `tests/test_template_test.py`.
- `uv run template-test` prints `Hello from template-test!` (single-command Typer app —
  no subcommand); `uv run pytest -q` passes.

Full mode additionally:

- `LICENSE` carries the license name, author, and current year.
- The initial commit contains no `.claude/` paths while `.claude/{CLAUDE.md,
  settings.json, hooks/}` exist on disk — the payload ships untracked by design.
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
