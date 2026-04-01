#!/bin/bash
# Scaffold a new Python project from proj-template.
#
# Copies the template, replaces PACKAGE placeholders with the given name,
# initializes git, installs dependencies, and makes the initial commit.
#
# Usage: proj-init.sh <path>
#   path  Target directory (e.g., ~/repos/gdrive). Basename becomes the package name.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VERSION_FILE="$SCRIPT_DIR/VERSION"
REPO_URL="https://github.com/gitronald/proj-template.git"

show_help() {
    echo "Usage: proj-init.sh [--license <key>] <path>"
    echo ""
    echo "  path     Target directory (e.g., ~/repos/gdrive)"
    echo "           Basename becomes the package name."
    echo "  --license  License key (default: mit)"
    echo "             Run 'gh api licenses --jq .[].key' for options."
    echo "  --branch   Template branch to clone (default: main)"
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
while [[ $# -gt 0 ]]; do
    case "$1" in
        --license) LICENSE="$2"; shift 2 ;;
        --branch) BRANCH="$2"; shift 2 ;;
        *) DEST="$1"; shift ;;
    esac
done

if [ -z "${DEST:-}" ]; then
    echo "Error: path required"
    show_help
    exit 1
fi

NAME="$(basename "$DEST")"

echo "Scaffolding ${NAME} at ${DEST}"

# Clone template to a temp directory
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT
git clone --quiet --depth 1 --branch "$BRANCH" "$REPO_URL" "$TMPDIR/proj-template"
TEMPLATE_DIR="$TMPDIR/proj-template/template"

# Fails if DEST already exists (atomic guard)
mkdir "$DEST"
rsync -a --exclude='__pycache__' "$TEMPLATE_DIR/" "$DEST/"

# Rename all PACKAGE-named paths (deepest first to avoid moving parents before children)
find "$DEST" -name '*PACKAGE*' -depth | while read -r f; do
    mv "$f" "${f/PACKAGE/${NAME}}"
done

# Replace PACKAGE placeholder in file contents
grep -rl "PACKAGE" "$DEST" | while read -r f; do
    sed "s/PACKAGE/${NAME}/g" "$f" > "$f.tmp" && mv "$f.tmp" "$f"
done

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
uv run pre-commit install

git add -A
git commit -m "initial commit"

stanza init --yes

git checkout -b dev
git push -u origin dev

echo ""
echo "Done. Project ready at ${DEST}"
echo "  cd ${DEST}"
