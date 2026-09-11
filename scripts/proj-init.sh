#!/usr/bin/env bash
# Scaffold a new Python project from proj-template.
#
# Copies the template, replaces PROJECT__NAME placeholders with the given name and
# MODULE__NAME placeholders with its module form (dashes become underscores),
# initializes git, installs dependencies, and makes the initial commit.
#
# Usage: proj-init.sh <path>
#   path  Target directory (e.g., ~/repos/gdrive). Basename becomes the project name.
#
# Targets bash 3.2+ (stock macOS /bin/bash), not POSIX sh. Under a shell that is
# not bash at all (dash, zsh), the first bash-only line would fail with a
# cryptic error; fail with a sentence instead. macOS /bin/sh is bash in POSIX
# mode, so "sh proj-init.sh" sets BASH_VERSION there and simply runs. Keep this
# above set -euo pipefail: dash rejects "-o pipefail" before any later check.
if [ -z "${BASH_VERSION:-}" ]; then
    echo "Error: proj-init.sh requires bash; run it as 'bash proj-init.sh'" >&2
    exit 1
fi

# -u catches a typo'd or never-assigned variable instead of expanding it to "";
# -o pipefail makes a pipeline fail when any stage does, not just the last, so a
# failing producer can no longer be masked by a successful consumer.
set -euo pipefail
# The placeholder pass overwrites existing files ("cat tmp > f"). An inherited
# noclobber (via an exported SHELLOPTS) would make that redirect fail mid-scaffold.
set +o noclobber

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
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
    echo "Usage: proj-init.sh [--license <key>] [--source <repo>] [--branch <name>] [--deps <tool>] <path>"
    echo ""
    echo "  path     Target directory (e.g., ~/repos/gdrive)"
    echo "           Basename becomes the project name; dashes become"
    echo "           underscores in the Python module name."
    echo "  --license  License key (default: mit)"
    echo "             Run 'gh api licenses --jq .[].key' for options."
    echo "  --source   proj-template repo to clone: a local checkout path or a"
    echo "             git URL, e.g. a fork (default: the GitHub repo)."
    echo "             Only committed changes are cloned."
    echo "  --branch   Template branch to clone (default: the source's HEAD —"
    echo "             main on GitHub, or whatever branch a local --source"
    echo "             checkout has checked out)"
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
SOURCE=""
BRANCH=""
DEPS=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        # An empty value is rejected, not read as "not given": empty is how these
        # variables spell "use the default", so --branch "$UNSET" would otherwise
        # silently scaffold the default branch.
        --license) [ -n "${2:-}" ] || { echo "Error: --license requires a value"; exit 1; }; LICENSE="$2"; shift 2 ;;
        --source)  [ -n "${2:-}" ] || { echo "Error: --source requires a value"; exit 1; }; SOURCE="$2"; shift 2 ;;
        --branch)  [ -n "${2:-}" ] || { echo "Error: --branch requires a value"; exit 1; }; BRANCH="$2"; shift 2 ;;
        --deps)    [ -n "${2:-}" ] || { echo "Error: --deps requires a value"; exit 1; }; DEPS="$2"; shift 2 ;;
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
# tr rather than ${LICENSE,,}: the latter is bash 4 and a syntax error under the
# bash 3.2 that macOS ships as /bin/bash.
LICENSE="$(printf '%s' "$LICENSE" | tr '[:upper:]' '[:lower:]')"
if ! [[ "$LICENSE" =~ ^[a-z0-9][a-z0-9.-]*$ ]]; then
    echo "Error: '--license ${LICENSE}' is not a valid license key"
    echo "Keys are lowercase, e.g. mit, apache-2.0, bsd-3-clause."
    echo "Run 'gh api licenses --jq .[].key' for the full list."
    exit 1
fi

# BRANCH is passed to git clone --branch. Let git decide what a valid ref name
# is rather than guessing: this rejects a leading "-" (which git would read as an
# option), embedded spaces, "..", and the other shapes git itself refuses.
if [ -n "$BRANCH" ] && ! git check-ref-format --branch "$BRANCH" > /dev/null 2>&1; then
    echo "Error: '--branch ${BRANCH}' is not a valid git branch name"
    exit 1
fi

# Clone rather than copy even for a local --source: a clone carries exactly the
# committed tree a GitHub scaffold would, where a copy of a checkout's template/
# would also sweep in gitignored strays (a template/uv.lock, a .venv). A plain
# path makes git do a local clone, which ignores --depth with a warning;
# --no-local (below) takes the normal transport and honors it, and git ignores
# the flag for a URL. Pass the path through as given rather than building a
# file:// URL from it: git percent-decodes a URL, so a "%41" in the path would
# name a different directory.
CLONE_URL="${SOURCE:-$REPO_URL}"

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
# interpolated into sed unescaped (the placeholder substitution below), and
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
# "--" keeps a --source value starting with "-" from being read as a git option.
if [ -n "$BRANCH" ]; then
    git clone --quiet --no-local --depth 1 --branch "$BRANCH" -- "$CLONE_URL" "$TEMPLATE_TMP/proj-template"
else
    git clone --quiet --no-local --depth 1 -- "$CLONE_URL" "$TEMPLATE_TMP/proj-template"
fi
TEMPLATE_DIR="$TEMPLATE_TMP/proj-template/template"

# Check the clone is a proj-template this script can fill in before creating
# anything. A --source that is not one, a remote whose HEAD names a missing
# branch (git clones it "empty" and exits 0), or a release that predates the
# MODULE__NAME placeholders would otherwise fail late, in rsync or uv sync, and
# leave a half-built DEST that blocks every re-run.
if [ ! -d "$TEMPLATE_DIR/MODULE__NAME" ]; then
    echo "Error: ${CLONE_URL}${BRANCH:+ (branch ${BRANCH})} has no template/MODULE__NAME/"
    echo "It is not a proj-template repo, or is a release older than this script."
    exit 1
fi
# Without --branch the clone takes the source's HEAD, which for a local checkout
# is whatever it has checked out, so say which commit this scaffold comes from.
echo "Template: ${CLONE_URL} at $(git -C "$TEMPLATE_TMP/proj-template" rev-parse HEAD)"

# Fails if DEST already exists (atomic guard)
mkdir "$DEST"
rsync -a --exclude='__pycache__' "$TEMPLATE_DIR/" "$DEST/"

# Keep only the chosen dependency-update automation; drop the other.
if [ "$DEPS" = "renovate" ]; then
    rm -f "$DEST/.github/dependabot.yml"
else
    rm -f "$DEST/.github/renovate.json" "$DEST/.github/workflows/renovate.yml"
fi

# Rename all MODULE__NAME-named paths (deepest first to avoid moving parents
# before children). Rewrite only the basename: "${f/MODULE__NAME/...}" replaces
# the first match anywhere in the path, so a DEST that itself sits under a
# directory with the placeholder in its name would have its parent rewritten and
# the mv would fail.
find "$DEST" -depth -name '*MODULE__NAME*' | while read -r f; do
    mv "$f" "$(dirname "$f")/$(basename "$f" | sed "s/MODULE__NAME/${MOD_NAME}/")"
done

# Replace placeholders in file contents: MODULE__NAME = module name,
# PROJECT__NAME = project name. The spellings are load-bearing. The old bare
# PROJECT also matched inside CLAUDE_PROJECT_DIR, so it needed \b word
# boundaries — and \b is a GNU extension that BSD sed on macOS reads as a
# literal "b", so nothing matched and placeholders shipped silently.
# PROJECT__NAME cannot occur inside another token, so a plain literal match is
# correct on every platform; it is also still a valid package name, which keeps
# template/ resolvable as a uv project. Do not shorten it to __PROJECT__: uv
# rejects names that start or end with "_".
# grep exits 1 when nothing matches, which is legitimate here but which pipefail
# would turn into an abort — so tolerate exit 1 specifically and let a real grep
# failure (exit 2) still stop the scaffold. Reading the list from a variable
# rather than a pipeline also keeps the loop body in this shell, so a sed failure
# aborts instead of dying in a subshell.
placeholder_files="$(grep -rlF -e MODULE__NAME -e PROJECT__NAME "$DEST" || [ $? -eq 1 ])"
while IFS= read -r f; do
    [ -n "$f" ] || continue
    sed "s/MODULE__NAME/${MOD_NAME}/g; s/PROJECT__NAME/${NAME}/g" "$f" > "$f.tmp"
    # Copy back with cat, not mv. mv installs the temp file's inode with default
    # permissions, which strips the executable bit (0.9.2 fixed exactly that for
    # .claude/hooks/lint-typecheck.sh); cat rewrites the original inode, so its
    # mode survives. sed -i would too, but GNU and BSD sed spell it differently.
    cat "$f.tmp" > "$f"
    rm -f "$f.tmp"
done <<< "$placeholder_files"

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
