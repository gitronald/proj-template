---
status: draft
branch: feature/add-renovate
created: 2026-06-05T18:03:46-07:00
completed:
pr:
---

# Add security-hardened Renovate dependency automation to the template

## Plan

Add [Renovate](https://docs.renovatebot.com) as the default dependency-update automation
for `proj-template`. The repo currently has **no `.github/` directory** — no workflows and
no `dependabot.yml` — so this is greenfield, not a migration. Because this is the **template**,
whatever lands here propagates to every project scaffolded from it, so the security posture
matters more than for a single repo: a weak default is inherited everywhere.

### Why Renovate over Dependabot

Renovate covers the things the house workflow keeps wanting and Dependabot does weakly:
`baseBranches: ["dev"]` (target the active branch directly — no retarget dance), strong
per-ecosystem grouping, declarative cooldown (`minimumReleaseAge`), and ongoing SHA-pinning
of actions (`helpers:pinGitHubActionDigests`). See the deepreview discussion for the full
comparison.

### Decision: hosted app vs. self-hosted workflow

- **Hosted Mend Renovate app** — zero setup, free, PRs trigger CI, but grants a third-party
  app write access to every derived repo.
- **Self-hosted `renovatebot/github-action`** — a committed `renovate.yml` + `renovate.json`
  that reproduce in every child repo, full control, PRs trigger CI when run with a GitHub
  App / PAT token (not `GITHUB_TOKEN`); cost is owning the token + runner.

Lean: **self-hosted**, because a template benefits from config that travels with the repo and
from keeping the trust boundary in-house. Confirm before implementing.

### Files to add

- `.github/renovate.json` — config (baseline below).
- `.github/workflows/renovate.yml` — scheduled self-hosted run (weekly cron + `workflow_dispatch`),
  using a scoped GitHub App token from secrets.

### Baseline config (house conventions)

- `extends: ["config:recommended", "helpers:pinGitHubActionDigests"]`
- `baseBranches: ["dev"]`
- Group per ecosystem (Python deps; `github-actions`).
- Verify Renovate's **uv lockfile** support maturity against current docs before relying on it.

### Security hardening — the crux

Grounded in **GitGuardian, "Renovate & Dependabot: The New Malware Delivery System"**
(<https://blog.gitguardian.com/renovate-dependabot-the-new-malware-delivery-system/>). The
article documents update bots being abused as a malware delivery path — e.g. the malicious
`axios 1.14.1` reached production across ~895 repos in under an hour, 95 PRs **auto-merged with
no human interaction** — and a SHA/digest-mutation vector (the `trivy-action` case) where a bot
silently repoints a "pinned" digest. Mitigations to bake into the template default:

- **Cooldown / seasoning** — `minimumReleaseAge: "5 days"` (article suggests 3–5) plus
  `minimumReleaseAgeBehaviour: "timestamp-required"`. Reinforce at the package-manager layer too
  (uv `exclude-newer`), so an AI agent running `uv add`/`lock` can't trivially bypass it.
- **No auto-merge of bot PRs** — require human review; do not key any automerge on
  `pull_request.user.login == 'dependabot[bot]'` / Renovate. If automerge is ever enabled, scope
  it to vetted low-risk update types only.
- **Block digest mutation on workflows** — disable the `pinDigest` update type for
  `.github/workflows/**` so a bump can't silently move a pinned action SHA.
- **Least privilege** — minimal `permissions:` in the Renovate workflow; use `pull_request`
  (never `pull_request_target`, which would hand secrets to a malicious PR); scope the Renovate
  token to a GitHub App with least privileges, not a broad PAT.
- **CI must run on bot PRs** — run Renovate with the App/PAT token so update PRs actually trigger
  the test workflow (the `GITHUB_TOKEN`-doesn't-trigger-workflows limitation), and require green
  CI before merge.
- Optional last layer: a honeytoken as a tripwire.

### Keep native Dependabot *alerts* on

GitHub's Dependabot vulnerability **alerts** are a repo-setting, independent of who raises
update PRs. Renovate handling the updates does not disable them — leave them enabled for the
native advisory surface.

### Documentation: `docs/guides/github-automation.md`

Write a reference guide (alongside the existing `docs/guides/pre-commit.md` and
`trusted-publishers.md`) that records the **final** decisions and the reasoning behind them, so
derived projects inherit the *why*, not just the config. It covers:

- **Motivation** — why automate dependency updates, and the supply-chain risk that makes the
  hardening non-optional (summarize the GitGuardian findings + link).
- **Options considered** — Dependabot vs. Renovate; hosted app vs. self-hosted workflow; the
  tradeoffs of each.
- **Final choice** — what the template ships and why, with the security defaults (cooldown,
  no auto-merge, no workflow digest mutation, least-privilege token, CI on bot PRs) and their
  justification.

Treat it as the canonical reference that the `renovate.json` / workflow comments point back to.
(The original ask said `docs/guide/...`; using the existing plural `docs/guides/` to match
`pre-commit.md` and `trusted-publishers.md`.)

### Open questions

- Hosted app vs. self-hosted workflow (lean self-hosted — confirm).
- Renovate uv-lock support maturity.
- Automerge policy (lean: none) and exact cooldown window (5 days vs. 3).

## References

- GitGuardian — Renovate & Dependabot: The New Malware Delivery System:
  <https://blog.gitguardian.com/renovate-dependabot-the-new-malware-delivery-system/>
- Renovate docs: <https://docs.renovatebot.com>
