#!/bin/bash
# Portability guard: fail when a construct that breaks on macOS (bash 3.2, BSD
# sed/grep/awk) appears in any shell script in the repo. It catches a
# reintroduced GNU-ism on Linux, where every behavioral test would still pass.
#
# Comment lines are skipped, so a comment may name a banned construct to explain
# why it is avoided. Each rule carries sample lines it must match, checked
# before the scan, so a rule whose regex has rotted fails loudly instead of
# silently matching nothing.
#
# Usage: tests/portability.test.sh

# Every rule's regex and sample is a literal string, "$" included.
# shellcheck disable=SC2016
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
SELF="tests/portability.test.sh"

# Tracked plus untracked-but-not-ignored, so a new script is guarded before its
# first commit. -c still lists the tracked template/.claude/ payload even though
# that directory is ignored. -z lists paths raw: without it git C-quotes a
# non-ASCII path, which then names no file and would be skipped.
FILES="$(git -C "$ROOT" ls-files -z -co --exclude-standard -- '*.sh' | tr '\0' '\n' | grep -vxF "$SELF")"

FAILURES=0

# rule <description> <ERE> <sample line the ERE must match>...
rule() {
    local desc="$1" regex="$2" sample f hits rc
    shift 2
    for sample in "$@"; do
        if ! printf '%s\n' "$sample" | grep -qE -- "$regex"; then
            echo "Error: rule '$desc' does not match its own sample: $sample"
            FAILURES=$((FAILURES + 1))
            return
        fi
    done
    while IFS= read -r f; do
        [ -n "$f" ] || continue
        # grep exits 1 for no match; anything higher means the file was not
        # scanned, which must fail rather than read as clean.
        rc=0
        hits="$(grep -nE -- "$regex" "$ROOT/$f")" || rc=$?
        if [ "$rc" -gt 1 ]; then
            echo "Error: could not scan $f"
            FAILURES=$((FAILURES + 1))
            continue
        fi
        hits="$(printf '%s\n' "$hits" | grep -vE '^[0-9]+:[[:space:]]*#' || true)"
        if [ -n "$hits" ]; then
            echo "FAIL $desc"
            printf '%s\n' "$hits" | sed "s|^|     $f:|"
            FAILURES=$((FAILURES + 1))
        fi
    done <<< "$FILES"
}

rule "sed -i (in-place flag differs between GNU and BSD sed; write a temp file and cat it back)" \
    'sed([[:space:]]+-[A-Za-z]+)*[[:space:]]+(-[A-Za-z]*i|--in-place)' \
    'sed -i "s/a/b/" f' 'sed -E -i "s/a/b/" f'
rule "sed -r (GNU-only spelling; use sed -E)" \
    'sed[[:space:]]+-[A-Za-z]*r' 'sed -r "s/a+/b/" f'
rule "\\b \\s \\d \\w in a regex (GNU extensions; use POSIX classes or literal matches)" \
    '(sed|grep|awk|=~).*\\[bBsSdDwW]' "grep -E '\\bfoo\\b' f"
rule "GNU BRE escapes \\| \\+ \\? \\< \\> (BSD sed/grep read them as literals; use -E with plain | + ?)" \
    '(sed|grep).*\\[|+?<>]' "sed 's/a\\|b/x/' f" "sed 's/a\\+/x/' f" "grep '\\<foo\\>' f"
rule "regex interval {n,m} (old BSD awk rejects it; spell out the repetition)" \
    '(sed|grep|awk|=~).*[^$]\{[0-9]+(,[0-9]*)?\}' "grep -E 'a{0,1}' f"
rule "bash 4 case modification (\${v,,} \${v^^} \${a[i],,}; use tr)" \
    '\$\{[A-Za-z_][A-Za-z0-9_]*(\[[^]]*\])?(,|\^)' 'x="${v,,}"' 'x="${arr[0]^^}"'
rule "mapfile / readarray (bash 4)" \
    '(^|[^[:alnum:]_])(mapfile|readarray)([^[:alnum:]_]|$)' 'mapfile -t lines < f'
rule "associative array (bash 4)" \
    '(declare|local|typeset)[[:space:]]+-[A-Za-z]*A' 'declare -A map'
rule "script dir from bare \$0 (use \${BASH_SOURCE[0]:-\$0})" \
    'dirname[[:space:]]+"?\$0' 'dir="$(dirname "$0")"'

echo "Scanned $(printf '%s\n' "$FILES" | grep -c .) scripts"
if [ "$FAILURES" -ne 0 ]; then
    echo "Error: $FAILURES portability check(s) failed"
    exit 1
fi
echo "All portability checks passed"
