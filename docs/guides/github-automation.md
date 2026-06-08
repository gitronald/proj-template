# GitHub Automation

Projects created from this template include GitHub-side automation in
[`.github/`](../../template/.github/) — continuous integration, dependency updates, and
packaging. This guide is the canonical reference for what ships and why; the config files
point back here.

| File | Trigger | What it does |
|------|---------|--------------|
| [`workflows/test.yml`](../../template/.github/workflows/test.yml) | Push or PR to `dev` or `main` | Installs deps with `uv`, then runs ruff lint, `ruff format --check`, `pyrefly check`, and `pytest --cov` across Python 3.11–3.14 |
| [`workflows/publish.yml`](../../template/.github/workflows/publish.yml) | Push of a `v*` tag | Builds the wheel and publishes to PyPI via Trusted Publishing — skipped unless the `PUBLISH_ENABLED` repository variable is `true` |
| [`dependabot.yml`](../../template/.github/dependabot.yml) **or** [`renovate.json`](../../template/.github/renovate.json) + [`workflows/renovate.yml`](../../template/.github/workflows/renovate.yml) | Weekly | Dependency-update PRs — **pick one at scaffold time** (`--deps`). Dependabot (default, zero setup) or self-hosted Renovate (opt-in, stronger hardening) |

## Tests (`test.yml`)

CI runs on every push and pull request targeting `dev` or `main`. It installs the project
with `uv` and runs the full quality gate — ruff lint, `ruff format --check`, `pyrefly check`,
and `pytest --cov` — across the Python 3.11–3.14 matrix. The same format and lint checks run
locally on each commit via [pre-commit](pre-commit.md).

## Publish (`publish.yml`)

Tag pushes (`v*`) build the wheel and publish to PyPI via Trusted Publishing (OIDC, no stored
tokens). It is disabled by default until you opt in. See [Trusted Publishers](trusted-publishers.md)
for the full setup — the PyPI publisher, the `pypi` environment, and the `PUBLISH_ENABLED` switch.

## Dependency updates — Dependabot or Renovate

Dependency-update automation is a **choice made when scaffolding** (`proj-init.sh --deps`):

- **`dependabot` (default)** — GitHub-native, zero setup. Ships `.github/dependabot.yml`.
- **`renovate` (opt-in)** — self-hosted Renovate with stronger supply-chain hardening, but it
  needs a one-time GitHub App + repo secrets before it runs. Ships `.github/renovate.json` and
  `.github/workflows/renovate.yml`.

`proj-init.sh` keeps only the chosen tool's files and removes the other, so a scaffolded repo runs
exactly one updater. Pass `--deps renovate` (or pick it at the interactive prompt) to opt in; omit
it for the Dependabot default. This section is the decision record for both, and the shipped
config files point back here.

> Both options assume GitHub's Dependabot vulnerability **alerts** stay enabled (see the end of
> this section) — alerts are a repo setting independent of which updater opens PRs.

### Dependabot (default)

`dependabot.yml` opens dependency-update PRs weekly, **grouped per ecosystem** — at most one PR
for `uv` (Python) deps and one for `github-actions`, not one per package. Grouping only takes
effect once `dependabot.yml` reaches the repository's **default branch** (Dependabot reads its
config from there), and PRs target that default branch. Zero setup: GitHub runs it natively, no
token or workflow required. The trade-offs that motivate the Renovate option — no release
cooldown, can't target `dev` directly, doesn't keep action SHA pins current — are spelled out
below.

### Renovate (opt-in)

If you scaffold with `--deps renovate`, the project uses [Renovate](https://docs.renovatebot.com)
run **self-hosted** from a scheduled workflow instead of Dependabot.

### Why automate at all — and why the hardening is non-optional

Keeping dependencies current closes known vulnerabilities and keeps upgrades small. But update
bots are themselves a supply-chain attack surface: GitGuardian's
[*Renovate & Dependabot: The New Malware Delivery System*](https://blog.gitguardian.com/renovate-dependabot-the-new-malware-delivery-system/)
documents the bot becoming the delivery path — a malicious `axios 1.14.1` reached production
across ~895 repos in under an hour, with **95 PRs auto-merged with no human in the loop**, plus a
digest-mutation vector where a "pinned" action SHA is silently repointed. Because this config
ships in a *template*, a weak default would be inherited by every project scaffolded from it, so
the defaults below are tuned for security first.

### Options considered

- **Dependabot vs. Renovate.** Dependabot grouping needs the config on the default branch and
  can't target `dev` directly, has no release cooldown, and won't keep action SHA pins current.
  Renovate does all three (`baseBranchPatterns`, `minimumReleaseAge`, `helpers:pinGitHubActionDigests`),
  with stronger per-ecosystem grouping. → **Renovate.**
- **Hosted Mend app vs. self-hosted workflow.** The hosted app is zero-setup but grants a
  third-party app write access to every derived repo. A self-hosted `renovate.yml` +
  `renovate.json` travel with the repo, keep the trust boundary in-house, and (run with an App
  token) make update PRs trigger CI. → **Self-hosted.**

### What ships, and the security defaults

`renovate.json` (`extends: config:recommended` + `helpers:pinGitHubActionDigests`):

- **`baseBranchPatterns: ["dev"]`** — PRs open against the active branch directly, no retarget dance.
- **Grouping** — one PR for Python (`pep621`) deps, one for `github-actions`.
- **Release cooldown** — `minimumReleaseAge: "5 days"` with
  `minimumReleaseAgeBehaviour: "timestamp-required"`. The cooldown gives a compromised release
  time to be caught and yanked before it can land. `timestamp-required` *fails closed*: a
  package-version update with no verifiable release timestamp is held in **Pending** on the
  Dependency Dashboard rather than raised silently. (Note: `minimumReleaseAge` support is geared
  to version updates from datasources that expose timestamps; coverage for `digest`/`pinDigest`
  update types is limited and shouldn't be relied on as a guarantee for GitHub Actions — those are
  handled by the next rule instead.)
- **No auto-merge** — there are no automerge rules; every bot PR requires human review. This is
  the direct counter to the auto-merge incident above.
- **No silent digest mutation in workflows** — the `digest` update type is disabled for
  `.github/workflows/**`, so Renovate won't re-point an already-pinned action to a *new SHA under
  the same tag* (the silent-mutation vector). Visible version bumps (`major`/`minor`/`patch`,
  which also update the `# vX.Y.Z` comment) still flow, and `helpers:pinGitHubActionDigests` still
  pins any newly added unpinned action (`pinDigest`).

`renovate.yml` (the runner):

- **Least privilege** — `GITHUB_TOKEN` is `contents: read`; Renovate authenticates with a scoped
  **GitHub App** token instead of a broad PAT. The App token also makes Renovate's PRs trigger
  the `test.yml` workflow (PRs opened with `GITHUB_TOKEN` don't), so update PRs land behind green
  CI. It runs on a weekly cron plus `workflow_dispatch`, never on `pull_request_target`.

> Actions in every workflow are pinned to commit SHAs (with a `# vX.Y.Z` comment) so a retagged
> or repointed release can't change what runs.

### Setup in a scaffolded project

The runner needs a GitHub App you own to mint a short-lived, least-privilege token at run time
(this is what makes Renovate's PRs trigger CI — see above). Creating the App is a one-time
browser step; the rest is `gh`. The App is reusable across repos under the same account — create
it once, then for each new repo just do steps 3–4 (install + secrets).

**1. Create the App** *(github.com UI — there is no `gh app create`)*

- Personal: **Settings → Developer settings → GitHub Apps → New GitHub App**
  (org-owned: **Org → Settings → Developer settings → GitHub Apps → New GitHub App**).
- **GitHub App name** — anything unique (e.g. `myname-renovate`); **Homepage URL** — the repo URL
  is fine.
- **Webhook** — **uncheck "Active"**. Renovate is pulled by the cron; it needs no webhook.
- **Repository permissions** (least privilege):
  - **Contents: Read and write**
  - **Pull requests: Read and write**
  - **Issues: Read and write** — required because the shipped `renovate.json` sets
    `dependencyDashboard: true`, and the Dependency Dashboard *is* a GitHub issue. Without it
    Renovate fails with `WARN: Could not ensure issue` / `integration-unauthorized` and never
    creates or updates the dashboard. (Renovate also uses issues to surface config-error and
    onboarding notices.)
  - **Dependabot alerts: Read-only** — lets Renovate read the repo's vulnerability alerts so it
    can raise prioritized **security-fix PRs** (and bypass the cooldown for them). Omitting it is
    not fatal — routine updates still work — but Renovate logs `WARN: Cannot access vulnerability
    alerts` on the Dependency Dashboard and never opens alert-driven security PRs. (Adding this to
    an App that's *already* installed requires re-approving the updated permission on the
    installation before it takes effect — GitHub prompts you via banner/email.)
  - **Workflows: Read and write** — *only* if Renovate should update files under
    `.github/workflows/`; omit otherwise.
  - **Metadata: Read-only** (auto-selected).
- **Where can this GitHub App be installed?** — "Only on this account".
- Click **Create GitHub App**, then note the **Client ID** shown in the **About** section of the
  App's General settings page (looks like `Iv23li…`). The workflow uses the Client ID, not the
  numeric App ID — `actions/create-github-app-token` deprecated the `app-id` input in favor of
  `client-id`.

**2. Generate a private key** *(UI)*

- On the App's settings page → **Private keys → Generate a private key**. A `.pem` file
  downloads — keep it secret; treat it like a password.

**3. Install the App** *(UI)*

This is separate from *creating* the App — a brand-new App exists but is installed on **zero**
repos until you do this.

- Go to **<https://github.com/settings/apps>** (Settings → Developer settings → GitHub Apps) and
  click the App.
- Click **Install App** in the left sidebar, then the **Install** button next to your account.
  *(If the App is already installed there, that button instead reads **Installed** / is greyed
  out — a quick way to check the current state. To change which repos it covers, use **Configure**
  instead, below.)*
- A **first-time** install opens a **"Choose an account to install ⟨App⟩ on"** screen — pick your
  account (**@you**).
- On the **Repository access** screen you **must** choose one:
  - **All repositories** — the App can act on every repo under the account, including future ones.
  - **Only select repositories** — add the target repo explicitly. This is the least-privilege
    choice; repeat it per repo as you enroll more.

  Then click **Install** (the button may read **Install & Authorize**).

For a repo added **later**, the App is already on the account, so there is no account screen —
open the App → **Install App** → **Configure** (or **Settings → Applications → ⟨App⟩ →
Configure**) and under **Repository access** add the new repo.

> **Symptom if this step is skipped:** the Renovate workflow fails fast at the **Generate … App
> token** step with `404 … /repos/OWNER/REPO/installation`. The credentials are valid (a bad
> Client ID / key would be `401`), but the App is not installed on that repo — add the repo to the
> installation and re-run.

**4. Store the two secrets** *(`gh`)*

The `.env` holds the **Client ID** (a value) and `RENOVATE_APP_PRIVATE_KEY_PATH`, the **path** to
the downloaded `.pem` — not the key text. So it takes two `gh secret set` calls: `--body` for the
ID, and a `<` redirect to stream the key *file's contents* in (the secret must be the PEM itself,
which is why a single `--env-file` push can't carry it):

```bash
source ~/.config/renovatabot/.env   # loads RENOVATE_CLIENT_ID + RENOVATE_APP_PRIVATE_KEY_PATH
gh secret set RENOVATE_CLIENT_ID       --repo OWNER/REPO --body "$RENOVATE_CLIENT_ID"
gh secret set RENOVATE_APP_PRIVATE_KEY --repo OWNER/REPO < "$RENOVATE_APP_PRIVATE_KEY_PATH"
```

**5. Run it** *(`gh`, or wait for the Monday cron)*

```bash
gh workflow run renovate.yml --repo OWNER/REPO
```

Renovate reads its config from, and bases its work on, the repository's **default branch**.
Scaffolded repos push `dev` first, so `dev` is the remote default and Renovate finds the shipped
`renovate.json` there — the first run starts opening update PRs against `dev` (and an onboarding PR
only if no config is detected). If you later switch the default branch to `main`, make sure
`renovate.json` exists there too, or Renovate won't find its config. Leave GitHub's Dependabot
vulnerability **alerts** enabled alongside this (see below).

> **Simpler alternative — a fine-grained PAT.** Instead of an App you can store a fine-grained
> personal access token (Contents + Pull requests RW on the repo) as a single `RENOVATE_TOKEN`
> secret and pass it as `token:` in `renovate.yml`. It is still UI-created but skips the App
> install dance. The trade-off is a longer-lived credential tied to a user account with a wider
> blast radius — fine for low-stakes repos, weaker than the App for anything shared.

### Reusing one App across repos

One App (one App ID + one private key) can back **every** repo with this structure — you create
it once and install it on as many repos as you like. The minted runtime token is still scoped to
the one repo running the workflow, so a shared key is not a shared blast radius. There are two
ways to distribute the credentials.

**Org repos — set the secrets once at the org.** No per-repo step; every repo in scope inherits
them:

```bash
gh secret set RENOVATE_CLIENT_ID       --org YOUR_ORG --visibility all --body "Iv23liXXXXXXXXXXXXXX"
gh secret set RENOVATE_APP_PRIVATE_KEY --org YOUR_ORG --visibility all < path/to/renovatabot-app.pem
```

**Personal repos — cache the credentials once, then two commands per repo.** Personal accounts
have no shared-secret mechanism, so keep the downloaded `.pem` on disk and stash two things in a
local dotenv: the **Client ID** and the **path to that `.pem`** (not the key text — a multi-line
PEM inlined into a dotenv is fragile, and the secret has to be the file's contents anyway). Build
the file once:

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

Then enrolling any new repo is the two-command form from step 4 — one for the ID, one piping the
key file (the key can't ride `--env-file`, which would push the *path* as the secret, not the PEM):

```bash
source ~/.config/renovatabot/.env
gh secret set RENOVATE_CLIENT_ID       --repo OWNER/REPO --body "$RENOVATE_CLIENT_ID"
gh secret set RENOVATE_APP_PRIVATE_KEY --repo OWNER/REPO < "$RENOVATE_APP_PRIVATE_KEY_PATH"
```

Notes:

- The `.env` and the `.pem` hold App credentials — `chmod 600` both (and `700` the dir, as above),
  and keep them out of any tracked dotfiles repo. For stronger hygiene, read the key from a secrets
  manager (1Password `op read`, `pass`, macOS Keychain) at enroll time instead of leaving it on disk.
- Keep the `.env` to *only* these two vars, and store an **absolute** path in
  `RENOVATE_APP_PRIVATE_KEY_PATH` (the `$HOME` expansion above) so `source` resolves it from any
  working directory.

> **Wrapped in a skill.** The per-repo enroll step is automated by `scripts/renovatabot-enroll.sh`
> (and the `renovatabot-enroll` skill): it pushes the secrets from your `.env`, keeps Dependabot
> vulnerability alerts on while turning its security-update PRs off so only Renovate opens PRs
> (`--no-dependabot-toggle` to skip), and triggers the first run. Enroll a repo with
> `scripts/renovatabot-enroll.sh <owner/repo>`. It reads this same `.env` (client ID + key path)
> and streams the key file into the secret, so the key-as-path layout above works as-is. This
> guide stays the source of truth for what it does and why.

To reinforce the cooldown at the resolver layer, you can pin `uv`'s `exclude-newer` to a recent
timestamp so a local `uv add`/`uv lock` can't pull a release younger than your cutoff. It takes a
fixed date, so it is left **out of the template default** (a frozen timestamp would rot); adopt it
per-project if you want that extra layer.

### Keep native Dependabot alerts on

GitHub's Dependabot vulnerability **alerts** are a repo-level setting, independent of who raises
update PRs. Renovate handling updates does not disable them — leave them enabled for the native
advisory surface.
