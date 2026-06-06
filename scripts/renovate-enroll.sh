#!/bin/bash
# Enroll a scaffolded repo in self-hosted Renovate: push the GitHub App secrets,
# normalize Dependabot so Renovate is the only bot opening PRs, and kick the first run.
#
# Reads the App credentials from a local .env (never committed, never printed). This
# script holds no secrets itself — it only orchestrates `gh`. The .env stays on your
# machine. See docs/guides/github-automation.md for how to create the App and the .env.
set -euo pipefail

CONFIG_DIR="${RENOVATE_CONFIG_DIR:-$HOME/.config/renovate}"
ENV_FILE="$CONFIG_DIR/.env"
TOGGLE_DEPENDABOT=true

show_help() {
    echo "Usage: renovate-enroll.sh [--no-dependabot-toggle] <owner/repo>"
    echo ""
    echo "Description: Enroll a repo in this template's self-hosted Renovate setup:"
    echo "  1. Push RENOVATE_CLIENT_ID + RENOVATE_APP_PRIVATE_KEY repo secrets from"
    echo "     \$RENOVATE_CONFIG_DIR/.env (default ~/.config/renovate/.env)."
    echo "  2. Keep Dependabot vulnerability alerts ON, turn its security-update PRs OFF,"
    echo "     so only Renovate opens PRs (needs repo admin; skip with --no-dependabot-toggle)."
    echo "  3. Trigger the first Renovate run (renovate.yml)."
    echo ""
    echo "Arguments:"
    echo "  owner/repo              Target repository (e.g., gitronald/gdrive)"
    echo ""
    echo "Options:"
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

REPO=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-dependabot-toggle) TOGGLE_DEPENDABOT=false; shift ;;
        -h|--help) show_help; exit 0 ;;
        --*) echo "Error: unknown option $1"; show_help; exit 1 ;;
        *)
            if [[ -n "$REPO" ]]; then
                echo "Error: unexpected extra argument '$1'"
                show_help
                exit 1
            fi
            REPO="$1"; shift ;;
    esac
done

if [[ -z "$REPO" ]]; then
    echo "Error: owner/repo required"
    show_help
    exit 1
fi

if [[ ! "$REPO" =~ ^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$ ]]; then
    echo "Error: repository must be in owner/repo form (got '$REPO')"
    exit 1
fi

# Preconditions — fail clearly before touching anything.
if ! command -v gh >/dev/null 2>&1; then
    echo "Error: gh (GitHub CLI) is not installed"
    exit 1
fi
if ! gh auth status >/dev/null 2>&1; then
    echo "Error: gh is not authenticated — run 'gh auth login'"
    exit 1
fi
if [[ ! -f "$ENV_FILE" ]]; then
    echo "Error: credentials file not found: $ENV_FILE"
    echo "Create it with RENOVATE_CLIENT_ID and RENOVATE_APP_PRIVATE_KEY (see"
    echo "docs/guides/github-automation.md, 'Reusing one App across repos')."
    exit 1
fi

echo "Enrolling ${REPO} in Renovate"

# 1. Push the App secrets verbatim from the .env. gh reads the file directly; values
#    are never echoed by this script.
echo "- Setting repo secrets from ${ENV_FILE}"
gh secret set --repo "$REPO" --env-file "$ENV_FILE"

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

# 3. Kick the first Renovate run.
echo "- Triggering the first Renovate run"
gh workflow run renovate.yml --repo "$REPO"

echo ""
echo "Done. ${REPO} enrolled."
echo "  Watch: gh run list --repo ${REPO} --workflow renovate.yml"
