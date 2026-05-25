#!/bin/bash
# Lint + type-check gate for the Claude Code Stop hook.
# Runs ruff (lint only, no formatting/mutation) and pyrefly; exits 2 with
# stderr output if either fails, so the agent sees the errors and continues.
set -u
fail=0
uv run ruff check . >&2 || fail=1
uv run pyrefly check >&2 || fail=1
[ "$fail" -eq 0 ] || exit 2
