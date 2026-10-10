#!/usr/bin/env bash
# Lint + type-check gate for the Claude Code Stop hook.
# Runs ruff (lint + format check, non-mutating) and pyrefly; exits 2 with
# stderr output if any fail, so the agent sees the errors and continues.
#
# The format check mirrors CI (test.yml runs `ruff format --check .`): the
# linter does not police layout -- quote style, wrapping, trailing-comma
# expansion -- so without it the gate stays green on code CI will reject.
#
# No `set -e`: every check must run so the agent sees all the errors at once,
# not just the first.
set -u

# Check the tree actually being worked in. The hook inherits the agent's cwd,
# which may be a subdirectory, or a git worktree under .worktrees/ with its own
# pyproject.toml and .venv -- that is what `uv run` must resolve against, not the
# main checkout. So walk up to the nearest project root. One exception: in a uv
# workspace a member package has its own pyproject.toml, and stopping there
# would lint only the member's subtree while the hook still passes. When the
# git toplevel of the cwd (the worktree root inside a worktree) declares a
# [tool.uv.workspace], check from there instead. A nested project that is not a
# workspace member keeps its own root. Fall back to CLAUDE_PROJECT_DIR when the
# cwd is outside any project (a scratch directory).
root=$PWD
while [ ! -f "$root/pyproject.toml" ] && [ "$root" != "/" ]; do
    root=$(dirname "$root")
done
top=$(git rev-parse --show-toplevel 2>/dev/null || true)
if [ -n "$top" ] && grep -q '^\[tool\.uv\.workspace\]' "$top/pyproject.toml" 2>/dev/null; then
    root=$top
fi
[ -f "$root/pyproject.toml" ] || root=${CLAUDE_PROJECT_DIR:-$PWD}
cd "$root" || {
    echo "Error: lint-typecheck hook could not enter $root" >&2
    exit 2
}

fail=0
uv run ruff check . >&2 || fail=1
uv run ruff format --check . >&2 || fail=1
uv run pyrefly check >&2 || fail=1
[ "$fail" -eq 0 ] || exit 2
