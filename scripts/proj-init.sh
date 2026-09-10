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
        *) DEST="$1"; shift ;;
    esac
done

if [ -z "${DEST:-}" ]; then
    echo "Error: path required"
    show_help
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
if ! [[ "$MOD_NAME" =~ ^[a-z_][a-z0-9_]*$ ]]; then
    echo "Error: '${NAME}' does not map to a valid Python module name (got '${MOD_NAME}')"
    echo "Use lowercase letters, digits, underscores, and dashes."
    exit 1
fi

echo "Scaffolding ${NAME} at ${DEST}"

# Clone template to a temp directory
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT
git clone --quiet --depth 1 --branch "$BRANCH" "$REPO_URL" "$TMPDIR/proj-template"
TEMPLATE_DIR="$TMPDIR/proj-template/template"

# Fails if DEST already exists (atomic guard)
mkdir "$DEST"
rsync -a --exclude='__pycache__' "$TEMPLATE_DIR/" "$DEST/"

# Keep only the chosen dependency-update automation; drop the other.
if [ "$DEPS" = "renovate" ]; then
    rm -f "$DEST/.github/dependabot.yml"
else
    rm -f "$DEST/.github/renovate.json" "$DEST/.github/workflows/renovate.yml"
fi

# Rename all MODULE-named paths (deepest first to avoid moving parents before children)
find "$DEST" -name '*MODULE*' -depth | while read -r f; do
    mv "$f" "${f/MODULE/${MOD_NAME}}"
done

# Replace placeholders in file contents: MODULE = module name, PROJECT = project name
grep -rlE "MODULE|PROJECT" "$DEST" | while read -r f; do
    sed "s/MODULE/${MOD_NAME}/g; s/PROJECT/${NAME}/g" "$f" > "$f.tmp" && mv "$f.tmp" "$f"
done

# Stamp [tool.proj-template] with the release actually scaffolded. Read VERSION
# from the clone, not $VERSION_FILE: the clone reflects --branch, which can
# differ from the local checkout's VERSION, and is the only copy present when
# this script runs from outside a clone.
TEMPLATE_VERSION="$(cat "$TMPDIR/proj-template/VERSION" 2>/dev/null || true)"
if [ -z "$TEMPLATE_VERSION" ]; then
    echo "Warning: template VERSION not found; stamping as 'unknown'"
    TEMPLATE_VERSION="unknown"
fi
sed "s/TEMPLATE_VERSION/${TEMPLATE_VERSION}/" "$DEST/pyproject.toml" \
    > "$DEST/pyproject.toml.tmp" && mv "$DEST/pyproject.toml.tmp" "$DEST/pyproject.toml"

# Fetch license from GitHub API
SPDX_ID=$(gh api "licenses/${LICENSE}" --jq '.spdx_id')
AUTHOR=$(gh api user --jq '.name')
YEAR=$(date +%Y)
gh api "licenses/${LICENSE}" --jq '.body' \
    | sed "s/\[year\]/${YEAR}/g; s/\[fullname\]/${AUTHOR}/g" \
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
