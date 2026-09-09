# GitHub Automation

Projects created from this template include GitHub-side automation in
[`.github/`](../../template/.github/) — continuous integration, dependency updates, and
packaging. This guide is the canonical reference for what ships and why; the config files
point back here.

| File | Trigger | What it does |
|------|---------|--------------|
| [`workflows/test.yml`](../../template/.github/workflows/test.yml) | Push or PR to `dev` or `main` | Installs deps with `uv`, then runs ruff lint, `ruff format --check`, `pyrefly check`, and `pytest` (with coverage via `addopts`) across Python 3.11–3.14 |
| [`workflows/publish.yml`](../../template/.github/workflows/publish.yml) | Push of a `v*` tag | Builds the wheel and publishes to PyPI via Trusted Publishing — skipped unless the `PUBLISH_ENABLED` repository variable is `true` |
| [`dependabot.yml`](../../template/.github/dependabot.yml) **or** [`renovate.json`](../../template/.github/renovate.json) + [`workflows/renovate.yml`](../../template/.github/workflows/renovate.yml) | Weekly | Dependency-update PRs — **pick one at scaffold time** (`--deps`). Dependabot (default, zero setup) or self-hosted Renovate (opt-in, stronger hardening) |

## Tests (`test.yml`)

CI runs on every push and pull request targeting `dev` or `main`. It installs the project
with `uv` and runs the full quality gate — ruff lint, `ruff format --check`, `pyrefly check`,
and `pytest` with coverage — across the Python 3.11–3.14 matrix. The same format and lint checks run
locally on each commit via [pre-commit](pre-commit.md).

## Publish (`publish.yml`)

Tag pushes (`v*`) build the wheel and publish to PyPI via Trusted Publishing (OIDC, no stored
tokens). It is disabled by default until you opt in. See [Trusted Publishers](trusted-publishers.md)
for the full setup — the PyPI publisher, the `pypi` environment, and the `PUBLISH_ENABLED` switch.

## Dependency updates — Dependabot or Renovate

Dependency-update automation is a **choice made when scaffolding** (`proj-init.sh --deps`):

- **`dependabot` (default)** — GitHub-native, zero setup. Ships `.github/dependabot.yml`.
- **`renovate` (opt-in)** — self-hosted Renovate with stronger supply-chain hardening, but it
  needs a one-time GitHub App + per-repo secrets before it runs. Ships `.github/renovate.json`
  and `.github/workflows/renovate.yml`.

`proj-init.sh` keeps only the chosen tool's files and removes the other, so a scaffolded repo runs
exactly one updater. This section is the decision record for both; the shipped config files point
back here.

> Either way, keep GitHub's Dependabot vulnerability **alerts** on (see [Dependabot
> coexistence](#dependabot-coexistence)) — alerts are a repo setting independent of which updater
> opens PRs.

### Dependabot (default)

`dependabot.yml` opens dependency-update PRs weekly, **grouped per ecosystem** (one PR for `uv`
Python deps, one for `github-actions`). Zero setup — GitHub runs it natively, no token or workflow.
It does keep action pins current, so the template ships workflow actions pinned to **commit SHAs**
with a `# vX.Y.Z` comment (e.g. `actions/checkout@3d3c42e…  # v7.0.1`); Dependabot bumps the SHA
and the comment together.

The shipped config sets **`target-branch: dev`**, so PRs open against the active branch rather than
the default one. Per GitHub's [options
reference](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference#target-branch-),
when `target-branch` is defined *"only manifest files on the target branch are checked for version
updates"* and *"all pull requests for version updates are opened targeting the specified branch"* —
so updates also resolve against the tree they will merge into, not against `main`.

What Dependabot genuinely cannot do is read its **config** from a non-default branch: the file
[must live](https://docs.github.com/en/code-security/concepts/supply-chain-security/about-the-dependabot-yml-file)
in `.github/` on the default branch. So `target-branch` changes where PRs land, but any edit to
`dependabot.yml` is inert until it reaches `main` — including the grouping and cooldown keys. The
one tradeoff: with `target-branch` set, that ecosystem's options stop applying to **security
updates**, which always use the default branch — moot here, since this template keeps Dependabot
security-update PRs off and uses alerts instead (see [Dependabot
coexistence](#dependabot-coexistence)).

### Renovate (opt-in)

Scaffolding with `--deps renovate` runs [Renovate](https://docs.renovatebot.com) **self-hosted**
from a scheduled workflow. Update bots are themselves a supply-chain attack surface — GitGuardian's
[*Renovate & Dependabot: The New Malware Delivery System*](https://blog.gitguardian.com/renovate-dependabot-the-new-malware-delivery-system/)
documents a malicious `axios 1.14.1` reaching production across ~895 repos in under an hour, **95
PRs auto-merged with no human in the loop**, plus a digest-mutation vector that silently repoints a
"pinned" action SHA. Because this config ships in a *template*, every derived repo inherits the
default, so it is tuned for security first. Self-hosted (rather than the hosted Mend app) keeps the
trust boundary in-house and travels with the repo; run with an App token, its PRs still trigger CI.

### What ships (security defaults)

`renovate.json` (`extends: config:recommended` + `helpers:pinGitHubActionDigests`):

- **`baseBranchPatterns: ["dev"]`** — PRs open against the active branch; the Renovate equivalent
  of Dependabot's `target-branch: dev`. Both tools still read their *config* from the default
  branch (see [Renovate setup](#renovate-setup)).
- **Per-ecosystem grouping** — one PR for Python (`pep621`) deps, one for `github-actions`.
- **Release cooldown** — `minimumReleaseAge: "5 days"` with
  `minimumReleaseAgeBehaviour: "timestamp-required"`, giving a compromised release time to be caught
  and yanked before it lands. `timestamp-required` *fails closed*: an update with no verifiable
  release timestamp is held in **Pending** on the Dependency Dashboard, not raised silently.
  (Coverage is geared to version updates; `digest`/`pinDigest` types are guarded by the next rule.)
- **No auto-merge** — every bot PR requires human review, the direct counter to the auto-merge incident.
- **No silent digest mutation in workflows** — the `digest` update type is disabled for
  `.github/workflows/**`, so an already-pinned action can't be repointed to a new SHA under the same
  tag. Visible version bumps still flow, and `helpers:pinGitHubActionDigests` still pins newly added
  unpinned actions.

`renovate.yml` (the runner): `GITHUB_TOKEN` is `contents: read`; Renovate authenticates with a
scoped **GitHub App** token (not a broad PAT), which also makes its PRs trigger `test.yml` so
updates land behind green CI. It runs on a weekly cron plus `workflow_dispatch`, never
`pull_request_target`. The template ships actions already pinned to commit-SHA digests (with a
`# vX.Y.Z` comment) so a retagged or repointed release can't change what runs;
`helpers:pinGitHubActionDigests` stays on as a backstop that pins any action later added by
bare tag.

### Renovate setup

Setup is a one-time **GitHub App** you create in the browser (there is no `gh app create`), then
per-repo enrollment. Enrollment is automated by the **`install-renovatabot` skill** (backed by
`scripts/renovatabot-enroll.sh`) — that is the source of truth for the per-repo steps. This section
covers the manual UI parts the skill can't do, plus the one-time credential cache it reads. The App
is reusable: create it once, then enroll each repo.

**1. Create the App** *(UI: **Settings → Developer settings → GitHub Apps → New GitHub App**; org-owned uses the org's Developer settings)*

- **Name** anything unique (e.g. `myname-renovate`); **Homepage URL** — the repo URL is fine.
- **Webhook** — uncheck **Active** (Renovate is cron-pulled; it needs no webhook).
- **Repository permissions** (least privilege):
  - **Contents: Read and write** — read refs and push update branches.
  - **Pull requests: Read and write** — open update PRs.
  - **Issues: Read and write** — the shipped `renovate.json` sets `dependencyDashboard: true`, and
    the dashboard *is* a GitHub issue; without it Renovate logs `Could not ensure issue` and never
    builds the dashboard (it also uses issues for config-error and onboarding notices).
  - **Commit statuses: Read and write** — the shipped `renovate.json` sets `minimumReleaseAge`, so
    Renovate records the cooldown as a `renovate/stability-days` commit status. Without it
    `setStability` throws `integration-unauthorized` and the branch aborts *before* the PR opens —
    you get a pushed `renovate/*` branch and no PR. Required whenever the cooldown is set (it is, by
    default).
  - **Dependabot alerts: Read-only** — lets Renovate read alerts to raise prioritized security-fix
    PRs (and bypass the cooldown for them). Omitting it isn't fatal (routine updates still work) but
    no alert-driven PRs are opened.
  - **Workflows: Read and write** — required for the shipped setup: Renovate manages the action pins
    in `.github/workflows/**` (`helpers:pinGitHubActionDigests` + the `github-actions` group), and
    GitHub gates workflow-file edits behind this scope *on top of* `Contents`. Without it an
    Actions-update branch pushes but the commit to the workflow file is rejected. Omit only if you
    scope Renovate off workflow files entirely.
  - **Administration: Read-only** *(optional)* — lets Renovate read the base branch's protection
    (`GET …/branches/{base}/protection`) to learn required status checks, which matters only for
    **automerge**. With automerge off (the default here), skip it: the call returns `403`, Renovate
    logs `Do not have permissions to detect branch-protection` and proceeds on defaults. It's a
    broad repo-admin scope, so don't grant it just to silence that one benign log line — revisit only
    if you enable automerge with required checks.
  - **Metadata: Read-only** (auto-selected).
- **Where can this App be installed?** — "Only on this account".
- Create it, then copy the **Client ID** from the App's **General** settings (`Iv23li…`). The
  workflow uses the Client ID, not the numeric App ID.

**2. Generate a private key** *(UI)* — App settings → **Private keys → Generate a private key**; a
`.pem` downloads. Treat it like a password.

**3. Install the App on the repo** *(UI)* — *creating* the App installs it on **zero** repos. Open
the App → **Install App** → **Install** next to your account, then under **Repository access** pick
**Only select repositories** (least privilege) and add the target repo — or **All repositories** to
cover every repo including future ones. For a repo added later, the App is already on the account:
App → **Install App** → **Configure** → add the repo.

> **If skipped:** the workflow fails fast at **Generate … App token** with `404 …
> /repos/OWNER/REPO/installation` — the credentials are valid (a bad key is `401`) but the App isn't
> installed on that repo. Add it and re-run.

**4. Cache the credentials once** *(local)* — the skill (and the manual commands below) read a
dotenv holding the **Client ID** and the **path** to the `.pem`, not the key text (an inlined
multi-line PEM is fragile, and the secret has to be the file's contents anyway):

```bash
mkdir -p ~/.config/renovatabot && chmod 700 ~/.config/renovatabot
mv ~/Downloads/your-app.*.private-key.pem ~/.config/renovatabot/renovatabot-app.pem
chmod 600 ~/.config/renovatabot/renovatabot-app.pem
{
  echo 'RENOVATE_CLIENT_ID=Iv23liXXXXXXXXXXXXXX'
  printf 'RENOVATE_APP_PRIVATE_KEY_PATH=%s/.config/renovatabot/renovatabot-app.pem\n' "$HOME"
} > ~/.config/renovatabot/.env
chmod 600 ~/.config/renovatabot/.env
```

`chmod 600` the `.env` and the `.pem`, keep them out of any tracked dotfiles repo, and store an
**absolute** key path so `source` resolves from any directory. For stronger hygiene, read the key
from a secrets manager (1Password `op read`, `pass`, Keychain) at enroll time instead of leaving it
on disk. **Org repos** can skip the cache entirely and set the secrets once at the org —
`gh secret set RENOVATE_CLIENT_ID --org YOUR_ORG --visibility all --body "Iv23li…"` and
`gh secret set RENOVATE_APP_PRIVATE_KEY --org YOUR_ORG --visibility all < path/to/renovatabot-app.pem`
— inherited by every repo in scope.

**5. Enroll each repo** *(skill)* — run the `install-renovatabot` skill, or the script directly:

```bash
scripts/renovatabot-enroll.sh <owner/repo>
```

It (1) pushes the two repo secrets, (2) normalizes Dependabot (alerts on, security-update PRs off —
see [coexistence](#dependabot-coexistence)), and (3) triggers the first run. See the skill for flags
(`--no-dependabot-toggle`, `--dry-run`, `--yes`). The manual equivalent, if you are not using the
script:

```bash
source ~/.config/renovatabot/.env
# 1. Secrets — stream the key file (the secret must be the PEM, so --env-file can't carry it)
gh secret set RENOVATE_CLIENT_ID       --repo OWNER/REPO --body "$RENOVATE_CLIENT_ID"
gh secret set RENOVATE_APP_PRIVATE_KEY --repo OWNER/REPO < "$RENOVATE_APP_PRIVATE_KEY_PATH"
# 2. Normalize Dependabot (needs repo admin): keep alerts on, turn security-update PRs off
gh api -X PUT    "/repos/OWNER/REPO/vulnerability-alerts"
gh api -X DELETE "/repos/OWNER/REPO/automated-security-fixes"
# 3. Trigger the first run (or wait for the weekly cron)
gh workflow run renovate.yml --repo OWNER/REPO
```

Renovate reads its config from, and bases its work on, the repository's **default branch**.
Scaffolded repos push `dev` first, so Renovate finds `renovate.json` there and opens update PRs
against `dev`. If you later make `main` the default, ensure `renovate.json` exists there too.

> **Simpler alternative — a fine-grained PAT.** Store a fine-grained PAT (Contents + Pull requests
> RW on the repo) as a single `RENOVATE_TOKEN` secret and pass it as `token:` in `renovate.yml`,
> skipping the App install. The trade-off is a longer-lived credential with a wider blast radius —
> fine for low-stakes repos, weaker than the App for anything shared.

To reinforce the cooldown at the resolver layer, you can pin `uv`'s `exclude-newer` per project; it
takes a fixed date, so it is left out of the template default (a frozen timestamp would rot).

### Dependabot coexistence

"Dependabot" is three independent features, and choosing Renovate touches all three:

- **Version updates** — the routine "keep deps current" PRs from `.github/dependabot.yml`. Dropped
  under `--deps renovate` (the file isn't shipped), so these never appear.
- **Vulnerability alerts** — advisory notices in the Security tab; a repo setting
  (`/repos/{o}/{r}/vulnerability-alerts`). **Keep on** — Renovate reads them to raise prioritized
  security-fix PRs (and bypasses the cooldown for those).
- **Security updates** — Dependabot's own auto-fix **PRs**; a separate repo setting
  (`/repos/{o}/{r}/automated-security-fixes`). **Turn off** with Renovate, or both bots open PRs for
  the same CVE.

Desired end state with Renovate: alerts **on**, Dependabot security-update PRs **off**, Renovate
owns every PR. Both are repo settings reachable via `gh api` and need repo **admin** — which is why
step 5 (and the skill) runs them under your own `gh` auth, not the least-privilege App token.

### Troubleshooting the first run

The runner fails in stages — mint the App token, init the repo, push the branch, set the stability
status, then open the PR — each mapping to a distinct permission gap. They **cascade**: fixing one
just surfaces the next, and every run still exits `0`, so grant the whole permission set up front
rather than chasing them across runs. Run with `-f logLevel=debug` (the `workflow_dispatch` input)
to see the per-branch decision behind an otherwise-green run.

- **`404 … /repos/OWNER/REPO/installation`** at "Generate … App token" — credentials are valid (a
  bad Client ID/key is `401`), but the App isn't installed on that repo (step 3).
- **`platform-unknown-error` at init, GraphQL `FORBIDDEN` on `["repository","defaultBranchRef"]`** —
  the App is missing **Contents**. Reading a branch ref needs it, and this bites **private** repos
  specifically: a public repo's refs are readable without `Contents`, so the same under-permissioned
  App inits fine on a public repo and hard-fails on a private one. Add **Contents: Read and write**,
  re-approve, and re-run with `-f logLevel=debug` (the `workflow_dispatch` input) to surface the
  GraphQL path.
- **Green run, dashboard issue but no update branch** — the App can maintain the dashboard (`Issues`
  RW) but can't push the update branch. It's missing **Contents** *write* (to push at all) or, since
  the template's updates edit `.github/workflows/**`, **Workflows** *write* (the commit to a workflow
  file is rejected even with `Contents`). Grant both as **Read and write**.
- **Green run, `renovate/*` branch pushed but no PR; debug shows `POST …/statuses/<sha>` → `403`
  with `x-accepted-github-permissions: statuses=write`** — the branch pushes, but Renovate can't set
  the `renovate/stability-days` status the `minimumReleaseAge` cooldown requires, so it aborts at
  `setStability` (`integration-unauthorized`) before opening the PR. Add **Commit statuses: Read and
  write**. This surfaces only *after* Contents/Workflows are fixed — the classic cascade.
- **Green run, branch and status fine but still no PR** — the App can push and set status but can't
  raise the PR; it's missing **Pull requests** *write*. Grant it as **Read and write**.

> **Re-approve after changing permissions.** A permission added to an already-installed App stays
> *pending* until you accept it — the App keeps running on the old set, so the symptoms above
> persist even after you tick the new box. This applies to **any** added permission. Re-approve via
> the banner/email GitHub sends, or App → **Install App** → **Configure**.
