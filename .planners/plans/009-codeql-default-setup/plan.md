---
id: 9
slug: codeql-default-setup
status: draft
branch:
created: 2026-11-06T20:37:41-08:00
concluded:
pr:
---

# Offer CodeQL default setup on public repos

## Plan

### Goal

Give public repos built from this template CodeQL code scanning, using GitHub's
**default setup**: a repository setting that GitHub runs and keeps current. Nothing
is added to `template/`. The template's job is to decide when to turn the setting on
and to check that it stays on; it ships no workflow file for it.

### Decisions

1. **Default setup, not a workflow.** An advanced-setup `codeql.yml` would put
   `github/codeql-action/*` pins in every repo, and the updater would bump them
   weekly. Default setup has no file, no pins, and no update PRs. It is one API call
   to turn on and one to check.
2. **Public repos only.** Code scanning is free on public repos. A private repo needs
   a paid GitHub Code Security license, so the setting is skipped there, and the
   output says why rather than trying and failing. A workflow shipped to every repo
   would need a gate like `PUBLISH_ENABLED` to stay quiet on private repos; a
   setting needs no such gate.
3. **The user decides, repo by repo.** The skill offers the setting and enables it
   only on a yes. It is never switched on silently.
4. **It lives in the `install-template` skill, beside the Dependabot repo settings.**
   `proj-init.sh` writes files and never touches GitHub settings (it does not even
   create the GitHub repo), so this is not a `proj-init.sh` flag.
5. **The guide is the record.** `docs/guides/github-automation.md` gets a short
   section on what default setup is, why it is on only for public repos, and why
   there is no workflow file. The skill points to that section.

### Commands

- Visibility: `gh repo view OWNER/REPO --json visibility --jq .visibility`
- State: `gh api repos/OWNER/REPO/code-scanning/default-setup --jq .state` reads
  `configured` or `not-configured`
- Enable: `gh api -X PATCH repos/OWNER/REPO/code-scanning/default-setup -f state=configured`
  (needs admin on the repo and GitHub Actions enabled; it starts a first analysis)

### Steps

1. **Check the API on one public repo.** Read the state, enable it, and read it
   again. Record which languages GitHub selects for a template-shaped repo. Expect
   `python`, and possibly `actions` too (GitHub Actions workflows as a CodeQL
   language, which would catch script injection in workflows); this is not yet
   verified. Record what the PATCH returns, how long the first analysis takes, and
   what happens on a repo that already has an advanced-setup CodeQL workflow (the
   two conflict).
2. **Mode 1 (new repo).** Add a follow-up step for once the repo exists on GitHub,
   in the same place as the `/install-renovatabot` follow-up: if the repo is public,
   offer default setup; if it is private, say it is skipped and why.
3. **Mode 2 (upgrade).** Next to the "Dependabot repo settings" sync note, add a
   CodeQL note: on a public repo, read the state; if it is `not-configured`, offer
   to enable it. This also catches a repo that went public after it was scaffolded,
   which Mode 1 never sees again. On a private repo, record "skipped (private)".
4. **The guide section** from decision 5, linked from both skill notes.
5. **Changelog entry** under `[Unreleased]`.

### Verification

- Step 1's results, logged.
- One upgrade pass on a public repo with the setting off: it offers, enables on a
  yes, and reads `configured` after.
- One upgrade pass on a private repo: it skips with the reason and makes no API
  write.

### Out of scope

- Shipping an advanced-setup CodeQL workflow in `template/`.
- Changing CodeQL on existing repos in bulk. Each repo gets the offer when its next
  upgrade runs.
- Code scanning on private repos, and buying a license for it.
- Triage of the alerts CodeQL raises; that is per-repo work.
