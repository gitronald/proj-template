#!/bin/bash
# Scaffold a new Python project from proj-template.
#
# Copies the template, replaces PACKAGE placeholders with the given name,
# initializes git, installs dependencies, and makes the initial commit.
#
# Usage: scaffold.sh <path>
#   path  Target directory (e.g., ~/repos/gdrive). Basename becomes the package name.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE_DIR="$SCRIPT_DIR"

show_help() {
    echo "Usage: scaffold.sh <path>"
    echo ""
    echo "  path  Target directory (e.g., ~/repos/gdrive)"
    echo "        Basename becomes the package name."
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
    show_help
    exit 0
fi

if [ -z "$1" ]; then
    echo "Error: path required"
    show_help
    exit 1
fi

DEST="$1"
NAME="$(basename "$DEST")"

if [ ! -d "$TEMPLATE_DIR" ]; then
    echo "Error: template not found at $TEMPLATE_DIR"
    exit 1
fi

echo "Scaffolding ${NAME} at ${DEST}"

# Fails if DEST already exists (atomic guard)
mkdir "$DEST"
rsync -a --exclude='__pycache__' --exclude='.git' --exclude='scaffold.sh' --exclude='README.md' "$TEMPLATE_DIR/" "$DEST/"

# Rename all PACKAGE-named paths (deepest first to avoid moving parents before children)
find "$DEST" -name '*PACKAGE*' -depth | while read -r f; do
    mv "$f" "${f/PACKAGE/${NAME}}"
done

# Replace PACKAGE placeholder in file contents
grep -rl "PACKAGE" "$DEST" | xargs sed -i "s/PACKAGE/${NAME}/g"

cd "$DEST"
git init
git checkout -b dev

uv sync --all-groups
uv run pre-commit install
stanza init

git add -A
git commit -m "initial commit"

echo ""
echo "Done. Project ready at ${DEST}"
echo "  cd ${DEST}"
