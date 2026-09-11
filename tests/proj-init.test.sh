#!/bin/bash
# Behavioral tests for scripts/proj-init.sh.
#
# Scaffolds from this checkout (--source) into a temp directory with gh, uv,
# stanza, and planners stubbed on PATH, so nothing touches the network or
# GitHub, then asserts on the result. Everything else is the real script: the
# clone, rsync, path renames, placeholder substitution, license insertion, git
# init, commit, and push.
#
# --source clones HEAD while the script under test is the working-tree copy, so
# the suite refuses to run over uncommitted changes to scripts/, template/, or
# VERSION: it would otherwise pair a script and a template that no commit
# contains, and report greens and reds that the commit would not.
#
# The script under test runs under /bin/bash — 3.2 on macOS — rather than
# whatever bash is first on PATH, since that is what a stock Mac has.
#
# Usage: tests/proj-init.test.sh
#   MANIFEST_OUT=<file>  also write a checksum manifest of the scaffolded tree,
#                        so CI can compare the Linux and macOS output.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
SCRIPT="$ROOT/scripts/proj-init.sh"
BASH_UNDER_TEST="${BASH_UNDER_TEST:-/bin/bash}"

if [ -n "$(git -C "$ROOT" status --porcelain -- scripts template VERSION)" ]; then
    echo "Error: uncommitted changes under scripts/, template/, or VERSION; commit them first"
    git -C "$ROOT" status --short -- scripts template VERSION
    exit 1
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

FAILURES=0
pass() { printf 'ok   %s\n' "$1"; }
fail() { printf 'FAIL %s\n' "$1"; FAILURES=$((FAILURES + 1)); }
# check <description> <command...>
check() {
    local desc="$1"
    shift
    if "$@"; then pass "$desc"; else fail "$desc"; fi
}

# --- Stubs ------------------------------------------------------------------

BIN="$WORK/bin"
mkdir -p "$BIN" "$WORK/remotes"

cat > "$BIN/gh" <<'EOF'
#!/bin/bash
# Stub: answers the three gh api calls proj-init.sh makes.
echo "gh $*" >> "$STUB_LOG"
case "$*" in
    "api user "*) echo "Test Author" ;;
    *"--jq .spdx_id") echo "MIT" ;;
    *"--jq .body") printf 'MIT License\n\nCopyright (c) [year] [fullname]\n' ;;
    *) echo "Error: gh stub got an unexpected call: $*" >&2; exit 1 ;;
esac
EOF

cat > "$BIN/uv" <<'EOF'
#!/bin/bash
# Stub: uv sync, uv run pre-commit install, and uv tool install are no-ops.
echo "uv $*" >> "$STUB_LOG"
EOF

cat > "$BIN/planners" <<'EOF'
#!/bin/bash
# Stub: present on PATH so proj-init.sh skips installing it.
echo "planners $*" >> "$STUB_LOG"
EOF

cat > "$BIN/stanza" <<'EOF'
#!/bin/bash
# Stub: the real stanza init creates the GitHub repo and its origin remote.
# Point origin at a local bare repo instead, so the script's push succeeds.
echo "stanza $*" >> "$STUB_LOG"
remote="$STUB_REMOTES/$(basename "$PWD").git"
git init --quiet --bare "$remote"
git remote add origin "$remote"
EOF

chmod +x "$BIN"/*

export PATH="$BIN:$PATH"
export STUB_LOG="$WORK/stub.log"
export STUB_REMOTES="$WORK/remotes"

# Isolate git from the machine's config (hooksPath, signing, default branch).
export GIT_CONFIG_GLOBAL="$WORK/gitconfig"
export GIT_CONFIG_NOSYSTEM=1
git config --global user.name "Test Author"
git config --global user.email "test@example.com"
git config --global init.defaultBranch main

# --- Helpers ----------------------------------------------------------------

# scaffold <name> <extra proj-init args...>; output goes to $WORK/<name>.log.
# A --source among the extra args overrides this checkout. stdin is /dev/null so
# a scaffold without --deps never waits on the interactive prompt.
scaffold() {
    local name="$1"
    shift
    (cd "$WORK" && "$BASH_UNDER_TEST" "$SCRIPT" --source "$ROOT" "$@" "$name") \
        < /dev/null > "$WORK/$name.log" 2>&1
}

# rejects <name> <expected error text> <extra proj-init args...>: the scaffold
# fails, prints that error — so an unrelated early failure cannot take the
# credit — and leaves nothing at $WORK/<name>.
rejects() {
    local name="$1" expected="$2"
    shift 2
    ! scaffold "$name" "$@" && grep -qF -- "$expected" "$WORK/$name.log" && [ ! -e "$WORK/$name" ]
}

# Look for the bare spellings too, word-bounded (-w, which BSD grep supports):
# a file the placeholder rename missed must still fail, while CLAUDE_PROJECT_DIR
# — where "PROJECT" sits between underscores — must not. grep exits 1 for no
# match; exit 2 (an unreadable file) fails the check rather than passing it.
no_placeholder_contents() {
    local rc=0
    grep -rlFw --exclude-dir=.git -e PROJECT -e MODULE -e PROJECT__NAME -e MODULE__NAME "$1" || rc=$?
    [ "$rc" -eq 1 ]
}

no_placeholder_paths() {
    [ -z "$(find "$1" -path "$1/.git" -prune -o \( -name '*PROJECT*' -o -name '*MODULE*' \) -print)" ]
}

version_stamped() {
    grep -A1 -F '[tool.proj-template]' "$1/pyproject.toml" | grep -qxF "version = \"$2\""
}

initial_commit() {
    [ "$(git -C "$1" log --format=%s main)" = "initial commit" ]
}

no_tracked_claude() {
    [ -z "$(git -C "$1" ls-files .claude)" ]
}

dev_pushed() {
    git -C "$1" rev-parse --verify -q origin/dev > /dev/null
}

runs_clean() {
    "$BASH_UNDER_TEST" "$SCRIPT" "$@" > /dev/null
}

# --- Tests ------------------------------------------------------------------

# shellcheck disable=SC2016  # $BASH_VERSION must expand in the bash under test
echo "proj-init.sh under $("$BASH_UNDER_TEST" -c 'echo "bash $BASH_VERSION"')"

check "--help runs clean" runs_clean --help
check "--version runs clean" runs_clean --version
check "invalid name is rejected before anything is created" \
    rejects Bad.Name "Error: 'Bad.Name' does not map to a valid Python module name" --deps dependabot
check "empty --branch is rejected" rejects empty-branch "Error: --branch requires a value" --branch ""
check "empty --source is rejected" rejects empty-source "Error: --source requires a value" --source ""

NOT_TEMPLATE="$WORK/not-a-template"
git init --quiet "$NOT_TEMPLATE"
git -C "$NOT_TEMPLATE" commit --quiet --allow-empty -m "empty"
check "a source with no template is rejected before anything is created" \
    rejects no-template "Error: $NOT_TEMPLATE has no template/MODULE__NAME/" \
    --deps dependabot --source "$NOT_TEMPLATE"

# Mixed-case license key exercises the case fold that used to be ${LICENSE,,}.
if scaffold template-test --license MIT --deps dependabot; then
    pass "scaffold exits 0"
else
    fail "scaffold exits 0"
    cat "$WORK/template-test.log"
    echo "Error: scaffold failed; skipping checks on its output"
    exit 1
fi
P="$WORK/template-test"
expected_version="$(git -C "$ROOT" show HEAD:VERSION)"

check "log names the template commit scaffolded" \
    grep -qF "$(git -C "$ROOT" rev-parse HEAD)" "$WORK/template-test.log"
check "no placeholder survives in file contents" no_placeholder_contents "$P"
check "no placeholder survives in paths" no_placeholder_paths "$P"
check "module dir renamed to template_test/" test -f "$P/template_test/cli.py"
check "test file renamed to test_template_test.py" test -f "$P/tests/test_template_test.py"
check ".claude/CLAUDE.md names the renamed package" grep -qxF 'template_test/' "$P/.claude/CLAUDE.md"
check "project name keeps its dash" grep -qxF 'name = "template-test"' "$P/pyproject.toml"
check "entry point maps dashed name to underscored module" \
    grep -qxF 'template-test = "template_test.cli:app"' "$P/pyproject.toml"
check "CLAUDE_PROJECT_DIR intact in .claude/settings.json" \
    grep -qF CLAUDE_PROJECT_DIR "$P/.claude/settings.json"
check "CLAUDE_PROJECT_DIR intact in the Stop hook" \
    grep -qF CLAUDE_PROJECT_DIR "$P/.claude/hooks/lint-typecheck.sh"
check "Stop hook is still executable" test -x "$P/.claude/hooks/lint-typecheck.sh"
check "[tool.proj-template] stamped with VERSION $expected_version" \
    version_stamped "$P" "$expected_version"
check "license key folded to lowercase" grep -qF "gh api licenses/mit " "$STUB_LOG"
check "license line inserted after readme" grep -qxF 'license = "MIT"' "$P/pyproject.toml"
check "LICENSE carries year and author" \
    grep -qF "Copyright (c) $(date +%Y) Test Author" "$P/LICENSE"
check "dependabot kept" test -f "$P/.github/dependabot.yml"
check "renovate dropped" test ! -e "$P/.github/renovate.json" -a ! -e "$P/.github/workflows/renovate.yml"
check "initial commit made" initial_commit "$P"
check "initial commit tracks no .claude/ paths" no_tracked_claude "$P"
check "dev pushed to origin" dev_pushed "$P"

if scaffold renovate-test --deps renovate; then
    pass "renovate scaffold exits 0"
    R="$WORK/renovate-test"
    check "renovate kept" test -f "$R/.github/renovate.json" -a -f "$R/.github/workflows/renovate.yml"
    check "dependabot dropped" test ! -e "$R/.github/dependabot.yml"
else
    fail "renovate scaffold exits 0"
    cat "$WORK/renovate-test.log"
fi

# A source whose template has an executable file carrying a placeholder. The
# stock template's executables carry none, so only this exercises the rewrite
# loop's copy-back keeping a 0755 mode. It scaffolds with noclobber exported,
# which that copy-back's overwrite must survive, and from a relative path
# holding "%41", which a file:// URL built from it would percent-decode to "A".
FIXTURE_SRC="$WORK/fix%41src"
git clone --quiet --no-local --depth 1 "$ROOT" "$FIXTURE_SRC"
printf '#!/bin/sh\necho PROJECT__NAME\n' > "$FIXTURE_SRC/template/exec-fixture.sh"
chmod +x "$FIXTURE_SRC/template/exec-fixture.sh"
git -C "$FIXTURE_SRC" add template/exec-fixture.sh
git -C "$FIXTURE_SRC" commit --quiet -m "add executable fixture"
if (set -o noclobber; export SHELLOPTS; scaffold fixture-test --deps dependabot --source 'fix%41src'); then
    pass "fixture scaffold exits 0 (noclobber exported, % in relative --source)"
    F="$WORK/fixture-test"
    check "executable fixture keeps its mode through substitution" test -x "$F/exec-fixture.sh"
    check "executable fixture's placeholder replaced" grep -qxF 'echo fixture-test' "$F/exec-fixture.sh"
else
    fail "fixture scaffold exits 0 (noclobber exported, % in relative --source)"
    cat "$WORK/fixture-test.log"
fi

if [ -n "${MANIFEST_OUT:-}" ]; then
    # Content hash plus executable bit per file, in a locale-independent order.
    (cd "$P" && find . -path ./.git -prune -o -type f -print | LC_ALL=C sort \
        | while IFS= read -r f; do
            if [ -x "$f" ]; then mode=x; else mode=-; fi
            printf '%s %s %s\n' "$mode" "$(shasum -a 256 < "$f" | cut -d' ' -f1)" "$f"
        done) > "$MANIFEST_OUT"
    echo "Wrote manifest to $MANIFEST_OUT"
fi

echo
if [ "$FAILURES" -ne 0 ]; then
    echo "Error: $FAILURES check(s) failed"
    exit 1
fi
echo "All checks passed"
