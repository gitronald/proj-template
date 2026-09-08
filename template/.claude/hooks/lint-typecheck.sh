#!/usr/bin/env bash
# Lint + type-check gate for the Claude Code Stop hook.
# Runs ruff (lint only, no formatting/mutation) and pyrefly; exits 2 with
# stderr output if either fails, so the agent sees the errors and continues.
#
# No `set -e`: both checks must run so the agent sees all the errors at once,
# not just the first.
set -u

# Check the tree actually being worked in. The hook inherits the agent's cwd,
# which may be a subdirectory, or a git worktree under .worktrees/ with its own
# pyproject.toml and .venv -- that is what `uv run` must resolve against, not the
# main checkout. So walk up to the nearest project root, and only fall back to
# CLAUDE_PROJECT_DIR when the cwd is outside any project (a scratch directory).
root=$PWD
while [ ! -f "$root/pyproject.toml" ] && [ "$root" != "/" ]; do
    root=$(dirname "$root")
done
[ -f "$root/pyproject.toml" ] || root=${CLAUDE_PROJECT_DIR:-$PWD}
cd "$root" || {
    echo "Error: lint-typecheck hook could not enter $root" >&2
    exit 2
}

fail=0
uv run ruff check . >&2 || fail=1
uv run pyrefly check >&2 || fail=1
[ "$fail" -eq 0 ] || exit 2
