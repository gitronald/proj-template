#!/bin/bash
# Enroll a repo in self-hosted Renovate: push the GitHub App secrets, normalize
# Dependabot so Renovate is the only bot opening PRs, and kick the first run.
#
# Reads the App credentials from a local .env (never committed, never printed). The
# .env holds RENOVATE_CLIENT_ID (a value) and RENOVATE_APP_PRIVATE_KEY_PATH (the path
# to the App's .pem key) — so the two secrets go up as two `gh secret set` calls:
# --body for the id, a `<` redirect to stream the key file's contents. This script
# holds no secrets itself; it only orchestrates `gh`. See
# docs/guides/github-automation.md for how to create the App and the .env.
set -euo pipefail

CONFIG_DIR="${RENOVATE_CONFIG_DIR:-$HOME/.config/renovatabot}"
ENV_FILE="$CONFIG_DIR/.env"
TOGGLE_DEPENDABOT=true
DRY_RUN=false
ASSUME_YES=false
REPO=""

error() { echo "Error: $*" >&2; exit 1; }

show_help() {
    echo "Usage: renovatabot-enroll.sh [options] [owner/repo]"
    echo ""
    echo "Description: Enroll a repo in this template's self-hosted Renovate setup:"
    echo "  1. Push RENOVATE_CLIENT_ID + RENOVATE_APP_PRIVATE_KEY repo secrets from"
    echo "     \$RENOVATE_CONFIG_DIR/.env (default ~/.config/renovatabot/.env). The .env stores"
    echo "     the client id and the path to the .pem (RENOVATE_APP_PRIVATE_KEY_PATH)."
    echo "  2. Keep Dependabot vulnerability alerts ON, turn its security-update PRs OFF,"
    echo "     so only Renovate opens PRs (needs repo admin; skip with --no-dependabot-toggle)."
    echo "  3. Trigger the first Renovate run (renovate.yml)."
    echo ""
    echo "Arguments:"
    echo "  owner/repo              Target repository. Optional — defaults to the git config"
    echo "                          user.name plus the current repo's directory name."
    echo ""
    echo "Options:"
    echo "  -n, --dry-run           Show what would happen; make no changes (no confirm needed)"
    echo "  -y, --yes               Skip the confirmation prompt"
    echo "  --no-dependabot-toggle  Skip step 2 (leave Dependabot settings untouched)"
    echo "  -h, --help              Show this help"
    echo ""
    echo "Preconditions: gh authenticated (admin on the repo unless --no-dependabot-toggle),"
    echo "the GitHub App already created and installed on the repo, and the .env present."
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    show_help
    exit 0
fi

while [[ $# -gt 0 ]]; do
    case "$1" in
        -n|--dry-run) DRY_RUN=true; shift ;;
        -y|--yes) ASSUME_YES=true; shift ;;
        --no-dependabot-toggle) TOGGLE_DEPENDABOT=false; shift ;;
        -h|--help) show_help; exit 0 ;;
        --*|-?) echo "Error: unknown option $1" >&2; show_help; exit 1 ;;
        *)
            if [[ -n "$REPO" ]]; then
                echo "Error: unexpected extra argument '$1'" >&2
                show_help
                exit 1
            fi
            REPO="$1"; shift ;;
    esac
done

# Resolve the target. Default: git config user.name (the owner) + the current repo's
# top-level directory name (the repo). An explicit owner/repo argument overrides both.
if [[ -z "$REPO" ]]; then
    owner="$(git config user.name 2>/dev/null || true)"
    toplevel="$(git rev-parse --show-toplevel 2>/dev/null || true)"
    if [[ -z "$owner" || -z "$toplevel" ]]; then
        error "could not derive owner/repo (need 'git config user.name' and to be inside a git repo); pass <owner/repo> explicitly"
    fi
    REPO="${owner}/$(basename "$toplevel")"
fi

if [[ ! "$REPO" =~ ^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$ ]]; then
    error "repository must be in owner/repo form (got '$REPO'); pass <owner/repo> explicitly"
fi

# Preconditions — fail clearly before touching anything. A dry run stays fully local,
# so it doesn't require gh auth.
command -v gh >/dev/null 2>&1 || error "gh (GitHub CLI) is not installed"
if ! $DRY_RUN; then
    gh auth status >/dev/null 2>&1 || error "gh is not authenticated — run 'gh auth login'"
fi
[[ -f "$ENV_FILE" ]] || error "credentials file not found: $ENV_FILE
Create it with RENOVATE_CLIENT_ID and RENOVATE_APP_PRIVATE_KEY_PATH (see
docs/guides/github-automation.md, 'Reusing one App across repos')."

# Read the two values from the .env without running its contents in our shell or
# polluting this script's namespace: source it in a subshell and print just the one
# var (captured here, never echoed to the terminal).
read_env_value() {
    local _name="$1"
    ( set +u; . "$ENV_FILE" >/dev/null 2>&1; printf '%s' "${!_name:-}" )
}
CLIENT_ID="$(read_env_value RENOVATE_CLIENT_ID)"
KEY_PATH="$(read_env_value RENOVATE_APP_PRIVATE_KEY_PATH)"

[[ -n "$CLIENT_ID" ]] || error "$ENV_FILE is missing/empty RENOVATE_CLIENT_ID"
[[ -n "$KEY_PATH" ]]  || error "$ENV_FILE is missing/empty RENOVATE_APP_PRIVATE_KEY_PATH"
[[ -r "$KEY_PATH" ]]  || error "private key file not found or unreadable: $KEY_PATH"

# Plan — shown before any change (and as the whole output of a dry run). No secret
# values here: the client id is captured but never printed; the key is a file path.
echo "Renovate enrollment plan for ${REPO}:"
echo "  - Secrets (from ${ENV_FILE}):"
echo "      RENOVATE_CLIENT_ID        <- value"
echo "      RENOVATE_APP_PRIVATE_KEY  <- ${KEY_PATH}"
if $TOGGLE_DEPENDABOT; then
    echo "  - Dependabot: keep alerts ON, turn security-update PRs OFF"
else
    echo "  - Dependabot: leave untouched (--no-dependabot-toggle)"
fi
echo "  - Trigger the first Renovate run (renovate.yml)"

if $DRY_RUN; then
    echo ""
    echo "Dry run — no changes made."
    exit 0
fi

if ! $ASSUME_YES; then
    [[ -t 0 ]] || error "not a TTY — re-run with --yes to confirm non-interactively, or --dry-run"
    read -r -p "Proceed? [y/N] " reply
    case "$reply" in
        y|Y|yes|Yes|YES) ;;
        *) echo "Aborted."; exit 0 ;;
    esac
fi

echo "Enrolling ${REPO} in Renovate"

# 1. Push the App secrets — two calls: the id as a value, the key streamed from its
#    file (the secret must be the PEM contents, not its path). Values are never echoed.
echo "- Setting repo secrets"
gh secret set RENOVATE_CLIENT_ID       --repo "$REPO" --body "$CLIENT_ID"
gh secret set RENOVATE_APP_PRIVATE_KEY --repo "$REPO" < "$KEY_PATH"

# 2. Normalize Dependabot so only Renovate opens PRs (needs repo admin, hence the
#    user's own gh auth rather than the least-privilege App token).
if [[ "$TOGGLE_DEPENDABOT" == true ]]; then
    # These need repo admin. If they fail, the secrets from step 1 are already set, so a
    # re-run (optionally with --no-dependabot-toggle) finishes the job — every step here is
    # idempotent — hence the actionable hint instead of a raw error.
    if ! gh api -X PUT "/repos/${REPO}/vulnerability-alerts" \
        || ! gh api -X DELETE "/repos/${REPO}/automated-security-fixes"; then
        echo "Error: could not change Dependabot settings on ${REPO} (needs repo admin)." >&2
        echo "Secrets are already set. Re-run with --no-dependabot-toggle to skip this step" >&2
        echo "(Renovate still works; Dependabot security PRs just stay on), or grant admin." >&2
        exit 1
    fi
    echo "- Dependabot vulnerability alerts ON, security-update PRs OFF"
else
    echo "- Skipping Dependabot toggle (--no-dependabot-toggle)"
fi

# 3. Kick the first Renovate run. The workflow must exist on the repo's default branch;
#    scaffolding with --deps renovate pushes dev (the default) with renovate.yml present.
echo "- Triggering the first Renovate run"
if ! gh workflow run renovate.yml --repo "$REPO"; then
    echo "Error: could not trigger renovate.yml on ${REPO}." >&2
    echo "Ensure renovate.yml exists on the repo's default branch (the template ships it on" >&2
    echo "dev). Secrets/settings are already applied — trigger it manually once it's present." >&2
    exit 1
fi

echo ""
echo "Done. ${REPO} enrolled."
echo "  Watch: gh run list --repo ${REPO} --workflow renovate.yml"
