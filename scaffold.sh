#!/bin/bash
# Scaffold a new Python project from proj-template.
#
# Copies the template, replaces PACKAGE placeholders with the given name,
# initializes git, installs dependencies, and makes the initial commit.
#
# Usage: scaffold.sh <path>
#   path  Target directory (e.g., ~/repos/gdrive). Basename becomes the package name.
set -e

REPO_URL="https://github.com/gitronald/proj-template.git"

show_help() {
    echo "Usage: scaffold.sh [--license <key>] <path>"
    echo ""
    echo "  path     Target directory (e.g., ~/repos/gdrive)"
    echo "           Basename becomes the package name."
    echo "  --license  License key (default: mit)"
    echo "             Run 'gh api licenses --jq .[].key' for options."
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
    show_help
    exit 0
fi

LICENSE="mit"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --license) LICENSE="$2"; shift 2 ;;
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
git clone --quiet --depth 1 "$REPO_URL" "$TMPDIR/proj-template"
TEMPLATE_DIR="$TMPDIR/proj-template/template"

# Fails if DEST already exists (atomic guard)
mkdir "$DEST"
rsync -a --exclude='__pycache__' "$TEMPLATE_DIR/" "$DEST/"

# Rename all PACKAGE-named paths (deepest first to avoid moving parents before children)
find "$DEST" -name '*PACKAGE*' -depth | while read -r f; do
    mv "$f" "${f/PACKAGE/${NAME}}"
done

# Replace PACKAGE placeholder in file contents
grep -rl "PACKAGE" "$DEST" | xargs sed -i "s/PACKAGE/${NAME}/g"

# Fetch license from GitHub API
SPDX_ID=$(gh api "licenses/${LICENSE}" --jq '.spdx_id')
AUTHOR=$(gh api user --jq '.name')
YEAR=$(date +%Y)
gh api "licenses/${LICENSE}" --jq '.body' \
    | sed "s/\[year\]/${YEAR}/g; s/\[fullname\]/${AUTHOR}/g" \
    > "$DEST/LICENSE"
sed -i "/^readme = /a license = \"${SPDX_ID}\"" "$DEST/pyproject.toml"

cd "$DEST"
git init
git checkout -b dev

uv sync --all-groups
uv run pre-commit install

git add -A
git commit -m "initial commit"

stanza init --yes

echo ""
echo "Done. Project ready at ${DEST}"
echo "  cd ${DEST}"
