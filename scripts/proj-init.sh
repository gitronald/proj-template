#!/usr/bin/env bash
# Scaffold a new Python project from proj-template.
#
# Copies the template, replaces PROJECT placeholders with the given name and
# MODULE placeholders with its module form (dashes become underscores),
# initializes git, installs dependencies, and makes the initial commit.
#
# Usage: proj-init.sh <path>
#   path  Target directory (e.g., ~/repos/gdrive). Basename becomes the project name.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VERSION_FILE="$SCRIPT_DIR/../VERSION"
REPO_URL="https://github.com/gitronald/proj-template.git"

# Escape sed's replacement-side metacharacters (\ / &) in a value before
# interpolating it into an s/// expression. Without this, a "/" breaks the
# expression (sed exits non-zero, aborting mid-scaffold under set -e) and an "&"
# silently expands to the matched text instead of inserting itself. Newlines get
# folded to spaces first: sed treats a literal newline in a replacement as an
# unterminated command, which set -e turns into the same mid-scaffold abort.
sed_escape() {
    printf '%s' "$1" | tr '\n\r' '  ' | sed -e 's|[\\/&]|\\&|g'
}

show_help() {
    echo "Usage: proj-init.sh [--license <key>] [--branch <name>] [--deps <tool>] <path>"
    echo ""
    echo "  path     Target directory (e.g., ~/repos/gdrive)"
    echo "           Basename becomes the project name; dashes become"
    echo "           underscores in the Python module name."
    echo "  --license  License key (default: mit)"
    echo "             Run 'gh api licenses --jq .[].key' for options."
    echo "  --branch   Template branch to clone (default: main)"
    echo "  --deps     Dependency-update automation: dependabot or renovate"
    echo "             (default: dependabot). 'renovate' needs a one-time GitHub"
    echo "             App + secrets; see docs/guides/github-automation.md."
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
    show_help
    exit 0
fi

if [ "${1:-}" = "-v" ] || [ "${1:-}" = "--version" ]; then
    if [ -f "$VERSION_FILE" ]; then
        echo "proj-init $(cat "$VERSION_FILE")"
    else
        echo "proj-init (version unknown — run from local clone for version info)"
    fi
    exit 0
fi

LICENSE="mit"
BRANCH="main"
DEPS=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --license) [ $# -ge 2 ] || { echo "Error: --license requires a value"; exit 1; }; LICENSE="$2"; shift 2 ;;
        --branch)  [ $# -ge 2 ] || { echo "Error: --branch requires a value"; exit 1; }; BRANCH="$2"; shift 2 ;;
        --deps)    [ $# -ge 2 ] || { echo "Error: --deps requires a value"; exit 1; }; DEPS="$2"; shift 2 ;;
        --*) echo "Error: unknown option $1"; show_help; exit 1 ;;
        *)
            # Reject a second path instead of silently scaffolding the last one.
            [ -z "${DEST:-}" ] || { echo "Error: unexpected extra argument '$1' (path already set to '${DEST}')"; exit 1; }
            DEST="$1"; shift ;;
    esac
done

if [ -z "${DEST:-}" ]; then
    echo "Error: path required"
    show_help
    exit 1
fi

# LICENSE is interpolated into the gh API path ("licenses/${LICENSE}"), so
# restrict it to the shape GitHub's license keys actually take (mit, apache-2.0,
# bsd-3-clause, cc0-1.0). Without this a value containing "/" or ".." walks the
# path and calls a different endpoint entirely, and a "?" appends a query string.
# The endpoint is case-insensitive, so fold case rather than rejecting "MIT".
LICENSE="${LICENSE,,}"
if ! [[ "$LICENSE" =~ ^[a-z0-9][a-z0-9.-]*$ ]]; then
    echo "Error: '--license ${LICENSE}' is not a valid license key"
    echo "Keys are lowercase, e.g. mit, apache-2.0, bsd-3-clause."
    echo "Run 'gh api licenses --jq .[].key' for the full list."
    exit 1
fi

# Choose the dependency-update automation. Dependabot is the zero-setup default;
# Renovate is opt-in (stronger hardening, but needs a one-time GitHub App + secrets).
case "$DEPS" in
    dependabot|renovate) ;;
    "")
        if [ -t 0 ]; then
            echo "Dependency-update automation:"
            echo "  1) dependabot  GitHub-native, zero setup (default)"
            echo "  2) renovate    self-hosted, stronger hardening; needs a one-time GitHub App + secrets"
            printf "Choose [1/2] (default 1): "
            read -r reply
            case "$reply" in
                2|renovate) DEPS="renovate" ;;
                *) DEPS="dependabot" ;;
            esac
        else
            DEPS="dependabot"
        fi
        ;;
    *) echo "Error: --deps must be 'dependabot' or 'renovate'"; exit 1 ;;
esac

NAME="$(basename "$DEST")"
MOD_NAME="${NAME//-/_}"
# This gate is load-bearing beyond module naming: NAME and MOD_NAME are later
# interpolated into sed unescaped (the MODULE/PROJECT substitution below), and
# MOD_NAME is NAME with "-" swapped to "_", so any sed metacharacter in NAME
# survives into MOD_NAME and is rejected here before those sed calls run. Keep
# the character class this strict, or escape those call sites with sed_escape.
if ! [[ "$MOD_NAME" =~ ^[a-z_][a-z0-9_]*$ ]]; then
    echo "Error: '${NAME}' does not map to a valid Python module name (got '${MOD_NAME}')"
    echo "Use lowercase letters, digits, underscores, and dashes."
    exit 1
fi

echo "Scaffolding ${NAME} at ${DEST}"

# Clone template to a temp directory
TEMPLATE_TMP=$(mktemp -d)
trap 'rm -rf "$TEMPLATE_TMP"' EXIT
git clone --quiet --depth 1 --branch "$BRANCH" "$REPO_URL" "$TEMPLATE_TMP/proj-template"
TEMPLATE_DIR="$TEMPLATE_TMP/proj-template/template"

# Fails if DEST already exists (atomic guard)
mkdir "$DEST"
rsync -a --exclude='__pycache__' "$TEMPLATE_DIR/" "$DEST/"

# Keep only the chosen dependency-update automation; drop the other.
if [ "$DEPS" = "renovate" ]; then
    rm -f "$DEST/.github/dependabot.yml"
else
    rm -f "$DEST/.github/renovate.json" "$DEST/.github/workflows/renovate.yml"
fi

# Rename all MODULE-named paths (deepest first to avoid moving parents before
# children). Rewrite only the basename: "${f/MODULE/...}" replaces the first
# match anywhere in the path, so a DEST that itself sits under a directory named
# MODULE would have its parent rewritten and the mv would fail.
find "$DEST" -name '*MODULE*' -depth | while read -r f; do
    mv "$f" "$(dirname "$f")/$(basename "$f" | sed "s/MODULE/${MOD_NAME}/")"
done

# Replace placeholders in file contents: MODULE = module name, PROJECT = project
# name. The \b word boundaries are load-bearing, not decoration: an unanchored
# s/PROJECT/.../g also rewrites CLAUDE_PROJECT_DIR in .claude/settings.json and
# .claude/hooks/lint-typecheck.sh, leaving the Stop hook pointed at an
# environment variable that no longer exists — it then silently falls back to the
# cwd, which is the exact bug that variable was introduced to fix. "_" is a word
# character, so \bPROJECT\b cannot match inside CLAUDE_PROJECT_DIR, while every
# real placeholder (bounded by quotes, slashes, dots, or spaces) still matches.
# sed -i edits in place so file modes survive; the previous
# "sed > tmp && mv tmp f" pattern dropped the executable bit from
# .claude/hooks/lint-typecheck.sh, which stops the hook from running at all.
grep -rlE '\bMODULE\b|\bPROJECT\b' "$DEST" | while read -r f; do
    sed -i "s/\bMODULE\b/${MOD_NAME}/g; s/\bPROJECT\b/${NAME}/g" "$f"
done

# Stamp [tool.proj-template] with the release actually scaffolded. Read VERSION
# from the clone, not $VERSION_FILE: the clone reflects --branch, which can
# differ from the local checkout's VERSION, and is the only copy present when
# this script runs from outside a clone.
TEMPLATE_VERSION="$(cat "$TEMPLATE_TMP/proj-template/VERSION" 2>/dev/null || true)"
if [ -z "$TEMPLATE_VERSION" ]; then
    echo "Warning: template VERSION not found; stamping as 'unknown'"
    TEMPLATE_VERSION="unknown"
fi
TEMPLATE_VERSION_ESC="$(sed_escape "$TEMPLATE_VERSION")"
sed "s/TEMPLATE_VERSION/${TEMPLATE_VERSION_ESC}/" "$DEST/pyproject.toml" \
    > "$DEST/pyproject.toml.tmp" && mv "$DEST/pyproject.toml.tmp" "$DEST/pyproject.toml"

# Fetch license from GitHub API. AUTHOR is a free-text GitHub display name, so
# it is the one value here that can legitimately contain sed metacharacters
# ("Ada / Lovelace", "Smith & Co") — escape it before interpolating.
SPDX_ID=$(gh api "licenses/${LICENSE}" --jq '.spdx_id')
# .name is null for accounts with no display name set, and jq renders that as the
# string "null" — fall back to the login rather than writing "Copyright (c) 2026
# null" into the license.
AUTHOR=$(gh api user --jq '.name // .login')
YEAR=$(date +%Y)
# Fetch into a variable first. As a pipeline, a failing gh api would leave sed to
# succeed on empty input, and the pipeline's exit status is sed's — so set -e
# would not fire and the repo would get a silently empty LICENSE. In a command
# substitution the failure aborts the script instead.
LICENSE_BODY=$(gh api "licenses/${LICENSE}" --jq '.body')
printf '%s\n' "$LICENSE_BODY" \
    | sed "s/\[year\]/${YEAR}/g; s/\[fullname\]/$(sed_escape "$AUTHOR")/g" \
    > "$DEST/LICENSE"
sed "/^readme = /a\\
license = \"${SPDX_ID}\"
" "$DEST/pyproject.toml" > "$DEST/pyproject.toml.tmp" && mv "$DEST/pyproject.toml.tmp" "$DEST/pyproject.toml"

cd "$DEST"
git init

uv sync --all-groups

# planners is a global uv tool, not a project dependency — the scaffolded
# pre-commit hook shells out to `planners` on PATH. Install it if missing.
if ! command -v planners > /dev/null 2>&1; then
    echo "Installing planners (global uv tool)"
    uv tool install planners
fi

uv run pre-commit install

git add -A
git commit -m "initial commit"

stanza init --yes

git checkout -b dev
git push -u origin dev

echo ""
echo "Done. Project ready at ${DEST}"
echo "  cd ${DEST}"
echo "  scaffolded from proj-template ${TEMPLATE_VERSION}"

if [ "$DEPS" = "renovate" ]; then
    echo ""
    echo "Renovate selected — one-time setup before it runs:"
    echo "  - Create/install a GitHub App, then add the RENOVATE_CLIENT_ID and"
    echo "    RENOVATE_APP_PRIVATE_KEY repo secrets."
    echo "  - See the Setup section of docs/guides/github-automation.md in proj-template."
fi
