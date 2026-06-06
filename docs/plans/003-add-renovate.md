---
status: in-progress
branch: claude/open-plan-recent-changes-vN6eW
created: 2026-06-05T18:03:46-07:00
completed:
pr:
---

# Add security-hardened Renovate dependency automation to the template

## Plan

Add [Renovate](https://docs.renovatebot.com) as the default dependency-update automation
for `proj-template`. The scaffold payload under `template/` **already ships
`template/.github/dependabot.yml` plus `test.yml`/`publish.yml` workflows** — that payload is
what `proj-init.sh` copies into each new project's `.github/`. So this is a **migration** (replace
the payload's Dependabot *updates* config with Renovate), not greenfield. Because it lives in the
template, whatever lands here propagates to every project scaffolded from it, so the security
posture matters more than for a single repo: a weak default is inherited everywhere.

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

### Files to change (in the `template/` payload, so scaffolded projects inherit them)

- **Remove** `template/.github/dependabot.yml` — its *updates* role is replaced by Renovate
  (Dependabot security **alerts** are a repo setting and stay; see below).
- **Add** `template/.github/renovate.json` — config (baseline below).
- **Add** `template/.github/workflows/renovate.yml` — scheduled self-hosted run (weekly cron +
  `workflow_dispatch`), using a scoped GitHub App token from secrets.
- **Leave** `template/.github/workflows/{test,publish}.yml` as-is — Renovate keeps their `uses:`
  pins current via `helpers:pinGitHubActionDigests`.

(Paths *inside* the shipped `renovate.json` — `baseBranches: ["dev"]`, `.github/workflows/**` —
are relative to the scaffolded child project, where `.github/` sits at the repo root.)

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

### Documentation: `docs/guides/github-automation.md` (parent docs, not the payload)

Write a reference guide in proj-template's **own** `docs/guides/` — the parent/maintainer docs,
alongside `pre-commit.md` and `trusted-publishers.md` — **not** `template/docs/guides/`. It's the
template's decision record, so it stays in the parent and is not shipped into every scaffolded
project. It records the **final** choices and the reasoning behind them:

- **Motivation** — why automate dependency updates, and the supply-chain risk that makes the
  hardening non-optional (summarize the GitGuardian findings + link).
- **Options considered** — Dependabot vs. Renovate; hosted app vs. self-hosted workflow; the
  tradeoffs of each.
- **Final choice** — what the payload ships and why, with the security defaults (cooldown,
  no auto-merge, no workflow digest mutation, least-privilege token, CI on bot PRs) and their
  justification.

Treat it as the canonical reference the payload's `renovate.json` / workflow comments point back
to. (The original ask said `docs/guide/...`; using the existing plural `docs/guides/`.)

### Open questions

- Hosted app vs. self-hosted workflow (lean self-hosted — confirm).
- Renovate uv-lock support maturity.
- Automerge policy (lean: none) and exact cooldown window (5 days vs. 3).

## References

- GitGuardian — Renovate & Dependabot: The New Malware Delivery System:
  <https://blog.gitguardian.com/renovate-dependabot-the-new-malware-delivery-system/>
- Renovate docs: <https://docs.renovatebot.com>

## Log

### 2026-06-06 — Review and implementation

Reviewed the plan against the current repo state, resolved the open questions, and implemented.

**State at review time (some groundwork already landed in `eb4465e`):**

- The `template/.github/` payload ships `dependabot.yml` (grouped `uv` + `github-actions`
  updates) and SHA-pinned `test.yml` / `publish.yml`. No `uv.lock` is committed — Python deps
  live in `pyproject.toml` `[project.dependencies]` + `[dependency-groups]`.
- `docs/guides/github-automation.md` already exists and already had a "Planned: migration to
  Renovate" section, so the guide is *updated into* the decision record rather than created.

**Open questions — resolved:**

- **Hosted vs. self-hosted → self-hosted.** Config travels with the repo and the trust boundary
  stays in-house, which is what a template wants. Ship `renovate.json` + a scheduled
  `renovate.yml`.
- **Automerge → none.** No automerge keys anywhere; every bot PR requires human review. This is
  the central GitGuardian mitigation (the axios incident auto-merged 95 PRs with no human).
- **Cooldown → 5 days**, with `minimumReleaseAgeBehaviour: "timestamp-required"`. Verified
  against current docs: `timestamp-required` is real (added in Renovate `41.150.0`, the default
  in v42). Its effect is *fail-closed* — updates lacking a release timestamp (some GitHub Action
  digest updates do) are held in "Pending" on the Dependency Dashboard instead of being raised
  silently. That is the desired safe behavior, documented in the guide.
- **uv-lock maturity.** The `pep621` manager covers `pyproject.toml` deps including
  `[dependency-groups]` (`matchManagers: ["pep621"]`); the separate `uv` lockfile manager is
  irrelevant here because the template commits no `uv.lock`.

**Config keys verified against current Renovate docs/discussions** (docs.renovatebot.com 403s to
WebFetch, so confirmed via WebSearch + the renovate GitHub discussions): `minimumReleaseAge`,
`minimumReleaseAgeBehaviour=timestamp-required`, and the `pep621` manager name.

**Action SHAs** resolved via `git ls-remote` (both lightweight tags):
`renovatebot/github-action` v46.1.14 → `693b9ef15eec82123529a37c782242f091365961`;
`actions/create-github-app-token` v3.2.0 → `bcd2ba49218906704ab6c1aa796996da409d3eb1`.

**Two deliberate deviations from the plan text:**

1. **No frozen `uv` `exclude-newer` baked into the template.** `exclude-newer` takes a fixed
   timestamp, so committing one would silently freeze *all* dependency resolution at a fixed
   date in every scaffolded project and rot immediately. The cooldown is enforced at the
   Renovate layer (`minimumReleaseAge`) instead; `exclude-newer` is documented in the guide as
   an opt-in reinforcement rather than a shipped default.
2. **The shipped `renovate.json` references the guide by full GitHub URL, not a relative path.**
   The guide is parent/maintainer-only (not shipped into children), so a relative
   `docs/guides/...` pointer would dangle in every scaffolded repo.

**Files changed:** removed `template/.github/dependabot.yml`; added
`template/.github/renovate.json` and `template/.github/workflows/renovate.yml`; rewrote the
dependency-updates section of `docs/guides/github-automation.md` into the decision record;
updated `CHANGELOG.md` and `TODO.md`.
