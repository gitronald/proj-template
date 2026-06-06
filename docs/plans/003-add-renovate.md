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

### Follow-up: an enrollment skill + script (parent repo, not the payload)

Per-repo enrollment is the only manual step left once the App exists (the guide's "Reusing one
App across repos" section). Wrap it in a Claude Code **skill** backed by a small **script** so
enrolling a freshly scaffolded repo is a single invocation instead of a checklist. This is a
maintainer tool — it lives in proj-template's **own** repo, not in the `template/` payload, so it
is not shipped into scaffolded projects.

- **Script** — `scripts/renovate-enroll.sh` (new top-level `scripts/` dir). Takes `OWNER/REPO`,
  reads credentials from `${RENOVATE_CONFIG_DIR:-$HOME/.config/renovate}/.env` (keys
  `RENOVATE_CLIENT_ID` + `RENOVATE_APP_PRIVATE_KEY`), and:
  1. sets the repo secrets via `gh secret set --repo OWNER/REPO --env-file "$envfile"`,
  2. normalizes the repo's native Dependabot state so Renovate is the only bot opening PRs
     (see "Dependabot coexistence" below) — `gh api -X PUT  /repos/OWNER/REPO/vulnerability-alerts`
     (keep advisory alerts on) and `gh api -X DELETE /repos/OWNER/REPO/automated-security-fixes`
     (turn off Dependabot's *security-update PRs*). Make this step opt-out via a flag
     (e.g. `--no-dependabot-toggle`), since it needs repo **admin** rights the Renovate App
     deliberately lacks — so it runs under the user's own `gh` auth, not the App token.
  3. triggers the first run via `gh workflow run renovate.yml --repo OWNER/REPO`.
  - Holds **no secrets itself** — only orchestration; the `.env` stays on the user's machine.
  - Preconditions: `gh` authenticated (with admin on the repo if step 2 is enabled), the App
    already created + installed on the target repo, and the `.env` present. Fail clearly
    (non-zero, usage message) when any is missing; never print secret values.
  - Keep it POSIX-ish `sh`/`bash`, `set -euo pipefail`, and small.
- **Skill** — `.claude/skills/renovate-enroll/SKILL.md` (project skill). Thin wrapper that
  invokes the script for a given repo and reports the result; description triggers on "enroll a
  repo in Renovate" / "set up Renovate secrets". Points back to this guide for setup context.
- **Docs** — flip the guide's "Coming as a skill" callout to document the shipped skill + script
  once they land.

### Dependabot coexistence (when the Renovate option is chosen)

"Dependabot" is three independent features; removing `dependabot.yml` only disables the first:

1. **Version updates** — routine "keep deps current" PRs, driven by `.github/dependabot.yml`.
   With `--deps renovate`, `proj-init.sh` doesn't ship that file, so these never appear.
2. **Vulnerability alerts** — advisory notifications in the Security tab (**not** PRs); a
   repo-level setting (`/repos/{o}/{r}/vulnerability-alerts`). **Keep ON** — Renovate consumes
   this data to raise prioritized security-fix PRs (and bypasses the cooldown for them).
3. **Security updates** — auto-fix **PRs** for known vulns; a separate repo-level setting
   (`/repos/{o}/{r}/automated-security-fixes`). **Turn OFF** when using Renovate, otherwise both
   bots open PRs for the same CVE. Renovate then owns *all* PRs (routine + security).

Desired end state for a Renovate repo: alerts **on**, Dependabot security-update PRs **off**,
Renovate opens everything. Both toggles are repo settings reachable via `gh api` (need repo
**admin**), which is why the enrollment script does them under the user's `gh` auth rather than
the least-privilege App. Caveat: Renovate's alert-driven PRs vary by ecosystem, so a more
conservative operator may leave Dependabot security updates on as a fallback and accept the
occasional duplicate PR — hence the script flag to skip the toggle.

### Open questions (resolved)

- ~~Hosted app vs. self-hosted workflow~~ → **self-hosted**, and now **opt-in** per scaffold
  (`--deps renovate`); Dependabot stays the default.
- ~~Renovate uv-lock support maturity~~ → moot; `pep621` manager covers `pyproject.toml`, no
  `uv.lock` is committed.
- ~~Automerge policy / cooldown window~~ → **no auto-merge**, **5-day** `minimumReleaseAge`.

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

### 2026-06-06 — Follow-ups from review discussion

- Expanded the guide's "Setup in a scaffolded project" into a full github.com UI walkthrough
  (create App → generate key → install) plus `gh` commands for secrets and the first run, and a
  fine-grained-PAT alternative.
- Added a "Reusing one App across repos" section: org secrets for org repos; a cached
  `~/.config/renovate/.env` fed to `gh secret set --env-file` (one command per repo) for personal
  accounts, with credential-hygiene caveats.
- **Scoped a new deliverable** (see "Follow-up: an enrollment skill + script" above): wrap the
  per-repo enroll step in a project skill (`.claude/skills/renovate-enroll/`) backed by
  `scripts/renovate-enroll.sh`. Maintainer tooling in the parent repo, not the `template/`
  payload. The guide currently carries a "Coming as a skill" callout to be flipped once it lands.
  **Not yet implemented** — tracked as the remaining work for this plan.

### 2026-06-06 — Direction change: keep Dependabot, make the updater a scaffold-time choice

Superseding the original "migration" framing (remove Dependabot, replace with Renovate): the
template now **ships both** and `proj-init.sh` picks one at scaffold time, so Renovate's one-time
App/secrets setup is opt-in rather than imposed on every new project.

- **Restored** `template/.github/dependabot.yml` to the payload (it is no longer removed).
- **`proj-init.sh`** gains `--deps dependabot|renovate` (default `dependabot`), with an
  interactive prompt when no flag is given and stdin is a TTY. After copying the payload it keeps
  only the chosen tool's files and deletes the other (`dependabot.yml` *or*
  `renovate.json` + `workflows/renovate.yml`), so a scaffolded repo runs exactly one updater.
  When `renovate` is chosen it prints the one-time App/secrets next-steps.
- **Guide** reframed: the dependency-updates section now documents the choice, with a Dependabot
  (default) subsection and the Renovate (opt-in) decision record; both assume native Dependabot
  alerts stay on.
- **CHANGELOG** entry reworded from "replacing" to an opt-in `--deps` choice with Dependabot as
  the default.
- The enrollment skill/script (above) still applies — it is the opt-in Renovate path's
  per-repo helper. Still **not yet implemented**.

### 2026-06-06 — PR #16 review fixes (Copilot reviewer)

All six review comments were valid; applied:

- **`client-id`, not `app-id`.** Confirmed via the action's `action.yml` at v3.2.0 that `app-id`
  carries `deprecationMessage: "Use 'client-id' instead."`. Switched `renovate.yml` to
  `client-id`, renamed the secret `RENOVATE_APP_ID` → `RENOVATE_CLIENT_ID`, and updated the guide
  (capture the App's **Client ID** from General settings) + the org/env-file recipes +
  `proj-init.sh` next-steps.
- **`digest` vs `pinDigest`.** The silent-SHA-mutation threat (re-pointing an already-pinned
  action under the same tag) is the `digest` update type; `pinDigest` only pins unpinned actions.
  Changed the workflow rule to disable `digest` (was `pinDigest`) and corrected its description;
  `helpers:pinGitHubActionDigests` still pins newly added unpinned actions.
- **`inputs` context on schedule.** `inputs.logLevel` is only populated on `workflow_dispatch`;
  switched to `github.event.inputs.logLevel || 'info'`, which resolves safely on cron runs.
- **Overstated cooldown guarantee.** Softened the guide: `minimumReleaseAge`/`timestamp-required`
  is a version-update protection; `digest`/`pinDigest` coverage is limited and not relied on —
  GitHub Actions are guarded by the `digest`-disable rule instead.
- **`show_help` usage line** now includes `--branch` (was omitted).

### 2026-06-06 — Captured Dependabot-coexistence model + enroll-script scope

From the review discussion, recorded the operational details that were decided but not yet in the
plan:

- Added a **"Dependabot coexistence"** subsection: Dependabot is three independent features —
  *version updates* (the `dependabot.yml` file, dropped under `--deps renovate`), *vulnerability
  alerts* (repo setting, **keep on** — Renovate reads them), and *security-update PRs* (repo
  setting, **turn off** so the two bots don't both PR the same CVE). Desired Renovate end state:
  alerts on, Dependabot security PRs off, Renovate owns all PRs.
- Expanded the **enrollment-script spec** with a step 2 that normalizes that state via
  `gh api` (`PUT vulnerability-alerts`, `DELETE automated-security-fixes`). Flagged that these
  need repo **admin** — so they run under the user's own `gh` auth, not the least-privilege App
  token — and made the step opt-out (`--no-dependabot-toggle`) for operators who prefer to keep
  Dependabot security updates as a fallback (Renovate's alert-driven PRs vary by ecosystem).
  Also pinned the `.env` key names to `RENOVATE_CLIENT_ID` + `RENOVATE_APP_PRIVATE_KEY`.
- Marked the **Open questions** resolved (self-hosted + opt-in; pep621 covers deps; no auto-merge;
  5-day cooldown).

Remaining work for this plan is unchanged: implement `scripts/renovate-enroll.sh` +
`.claude/skills/renovate-enroll/` (still **not yet implemented**).
