---
name: renovatabot-enroll
description: Enroll a scaffolded repo in this template's self-hosted Renovate — push the GitHub App secrets from a local .env, normalize Dependabot so only Renovate opens PRs, and trigger the first run. Use when the user wants to "enroll a repo in Renovate", "set up Renovate secrets", or activate Renovate after scaffolding with `proj-init.sh --deps renovate`.
---

# Renovatabot enroll

Thin wrapper around `scripts/renovatabot-enroll.sh`. It enrolls a repository in this template's
self-hosted Renovate setup in one step. The script holds **no secrets** — it reads the GitHub
App credentials from `${RENOVATE_CONFIG_DIR:-~/.config/renovatabot}/.env` and only orchestrates
`gh`. See `docs/guides/github-automation.md` for the full setup rationale.

## When to use

The user asks to enroll/activate Renovate on a repo, set up the Renovate App secrets, or
finish Renovate setup after scaffolding a project with `proj-init.sh --deps renovate`.

## Preconditions

- `gh` authenticated, with **admin** on the target repo (unless `--no-dependabot-toggle`).
- The GitHub App already created and installed on the repo (one-time, browser step).
- `~/.config/renovatabot/.env` present with `RENOVATE_CLIENT_ID` and `RENOVATE_APP_PRIVATE_KEY_PATH`.

If a precondition is missing, the script exits non-zero with a clear message — relay it and
point the user at the guide rather than guessing.

## How to run

Run the script with the target repo (ask the user for `owner/repo` if not given):

```bash
scripts/renovatabot-enroll.sh <owner/repo>
```

The script: (1) pushes the two secrets from the `.env`, (2) keeps Dependabot vulnerability
alerts on while turning its security-update PRs off so only Renovate opens PRs, and (3)
triggers the first Renovate run. Pass `--no-dependabot-toggle` to skip step 2 (the only step
that needs repo admin). Report the result and the `gh run list …` watch command it prints.

## SHA digest pinning

The template ships workflow actions pinned to specific version tags (Dependabot-friendly).
Enrollment is where the shift to SHA digests happens: the first Renovate run's
`helpers:pinGitHubActionDigests` preset opens a PR re-pinning every action to a commit SHA
with a `# vX.Y.Z` comment. Expect that PR after step 3 and tell the user to merge it — no
manual re-pinning step is needed.
