# GitHub Automation

Projects created from this template include GitHub-side automation in
[`.github/`](../../template/.github/) — continuous integration, dependency updates, and
packaging. This guide is the canonical reference for what ships and why; the config files
point back here.

| File | Trigger | What it does |
|------|---------|--------------|
| [`workflows/test.yml`](../../template/.github/workflows/test.yml) | Push or PR to `dev` or `main` | Installs deps with `uv`, then runs ruff lint, `ruff format --check`, `pyrefly check`, and `pytest --cov` across Python 3.11–3.14 |
| [`workflows/publish.yml`](../../template/.github/workflows/publish.yml) | Push of a `v*` tag | Builds the wheel and publishes to PyPI via Trusted Publishing — skipped unless the `PUBLISH_ENABLED` repository variable is `true` |
| [`renovate.json`](../../template/.github/renovate.json) + [`workflows/renovate.yml`](../../template/.github/workflows/renovate.yml) | Weekly cron + manual | Self-hosted Renovate: grouped, `dev`-targeted dependency-update PRs with a release cooldown and ongoing action SHA-pinning |

## Tests (`test.yml`)

CI runs on every push and pull request targeting `dev` or `main`. It installs the project
with `uv` and runs the full quality gate — ruff lint, `ruff format --check`, `pyrefly check`,
and `pytest --cov` — across the Python 3.11–3.14 matrix. The same format and lint checks run
locally on each commit via [pre-commit](pre-commit.md).

## Publish (`publish.yml`)

Tag pushes (`v*`) build the wheel and publish to PyPI via Trusted Publishing (OIDC, no stored
tokens). It is disabled by default until you opt in. See [Trusted Publishers](trusted-publishers.md)
for the full setup — the PyPI publisher, the `pypi` environment, and the `PUBLISH_ENABLED` switch.

## Dependency updates (`renovate.json` + `renovate.yml`)

Scaffolded projects use [Renovate](https://docs.renovatebot.com) for dependency updates, run
**self-hosted** from a scheduled workflow. This section is the decision record for that choice;
the shipped [`renovate.json`](../../template/.github/renovate.json) points back here.

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
  Renovate does all three (`baseBranches`, `minimumReleaseAge`, `helpers:pinGitHubActionDigests`),
  with stronger per-ecosystem grouping. → **Renovate.**
- **Hosted Mend app vs. self-hosted workflow.** The hosted app is zero-setup but grants a
  third-party app write access to every derived repo. A self-hosted `renovate.yml` +
  `renovate.json` travel with the repo, keep the trust boundary in-house, and (run with an App
  token) make update PRs trigger CI. → **Self-hosted.**

### What ships, and the security defaults

`renovate.json` (`extends: config:recommended` + `helpers:pinGitHubActionDigests`):

- **`baseBranches: ["dev"]`** — PRs open against the active branch directly, no retarget dance.
- **Grouping** — one PR for Python (`pep621`) deps, one for `github-actions`.
- **Release cooldown** — `minimumReleaseAge: "5 days"` with
  `minimumReleaseAgeBehaviour: "timestamp-required"`. The cooldown gives a compromised release
  time to be caught and yanked before it can land. `timestamp-required` *fails closed*: an update
  with no verifiable release timestamp is held in **Pending** on the Dependency Dashboard rather
  than raised silently — so action updates that lack a timestamp wait for a manual nudge.
- **No auto-merge** — there are no automerge rules; every bot PR requires human review. This is
  the direct counter to the auto-merge incident above.
- **No silent digest mutation in workflows** — `pinDigest` updates are disabled for
  `.github/workflows/**`, so a bump can't silently move an already-pinned action SHA. Visible
  version bumps (which also update the `# vX.Y.Z` comment) still flow.

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
it once, then for each new repo just do steps 4–5 (install + secrets).

**1. Create the App** *(github.com UI — there is no `gh app create`)*

- Personal: **Settings → Developer settings → GitHub Apps → New GitHub App**
  (org-owned: **Org → Settings → Developer settings → GitHub Apps → New GitHub App**).
- **GitHub App name** — anything unique (e.g. `myname-renovate`); **Homepage URL** — the repo URL
  is fine.
- **Webhook** — **uncheck "Active"**. Renovate is pulled by the cron; it needs no webhook.
- **Repository permissions** (least privilege):
  - **Contents: Read and write**
  - **Pull requests: Read and write**
  - **Workflows: Read and write** — *only* if Renovate should update files under
    `.github/workflows/`; omit otherwise.
  - **Metadata: Read-only** (auto-selected).
- **Where can this GitHub App be installed?** — "Only on this account".
- Click **Create GitHub App**, then note the **App ID** shown at the top of the App's settings
  page.

**2. Generate a private key** *(UI)*

- On the App's settings page → **Private keys → Generate a private key**. A `.pem` file
  downloads — keep it secret; treat it like a password.

**3. Install the App** *(UI)*

- App settings → **Install App** → choose the account → **Only select repositories** → pick the
  scaffolded repo → **Install**.

**4. Store the two secrets** *(`gh`)*

```bash
gh secret set RENOVATE_APP_ID --repo OWNER/REPO --body "123456"
gh secret set RENOVATE_APP_PRIVATE_KEY --repo OWNER/REPO < path/to/renovate-app.pem
```

**5. Run it** *(`gh`, or wait for the Monday cron)*

```bash
gh workflow run renovate.yml --repo OWNER/REPO
```

The first run opens a "Configure Renovate" onboarding PR against `dev`; merge it to activate.
Leave GitHub's Dependabot vulnerability **alerts** enabled alongside this (see below).

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
gh secret set RENOVATE_APP_ID          --org YOUR_ORG --visibility all --body "123456"
gh secret set RENOVATE_APP_PRIVATE_KEY --org YOUR_ORG --visibility all < path/to/renovate-app.pem
```

**Personal repos — cache the credentials once, then one command per repo.** Personal accounts
have no shared-secret mechanism, so stash the two values in a local dotenv file and feed it to
`gh secret set --env-file`, which sets every `NAME=value` in the file in a single call. Build the
file once from the downloaded key (the private key must be a double-quoted, real-multi-line value
so gh's dotenv parser keeps it intact):

```bash
mkdir -p ~/.config/renovate && chmod 700 ~/.config/renovate
{
  echo 'RENOVATE_APP_ID=123456'
  printf 'RENOVATE_APP_PRIVATE_KEY="%s"\n' "$(cat ~/Downloads/your-app.*.private-key.pem)"
} > ~/.config/renovate/.env
chmod 600 ~/.config/renovate/.env
```

Then enrolling any new repo is one command:

```bash
gh secret set --repo OWNER/REPO --env-file ~/.config/renovate/.env
```

Notes:

- The file holds App credentials — `chmod 600` it (and `700` the dir, as above), and keep it out
  of any tracked dotfiles repo. For stronger hygiene, read the key from a secrets manager (1Password
  `op read`, `pass`, macOS Keychain) at enroll time instead of leaving it on disk.
- `--env-file` stores each value **verbatim**, so put the real PEM in the file, not base64 (a
  base64 value would force a decode step into `renovate.yml`). Keep the file to *only* these two
  vars — every line becomes a secret.
- If an older `gh` chokes on the multi-line quoted value, fall back to the two-command form from
  step 4 (`--body` for the ID, `< app.pem` redirect for the key).

> **Coming as a skill.** The per-repo enroll step (`gh secret set --env-file …`, plus installing
> the App and kicking the first run) will be wrapped in a Claude Code skill backed by a small
> script, so enrolling a freshly scaffolded repo is a single invocation rather than a manual
> checklist. This guide stays the source of truth for what that script does and why.

To reinforce the cooldown at the resolver layer, you can pin `uv`'s `exclude-newer` to a recent
timestamp so a local `uv add`/`uv lock` can't pull a release younger than your cutoff. It takes a
fixed date, so it is left **out of the template default** (a frozen timestamp would rot); adopt it
per-project if you want that extra layer.

### Keep native Dependabot alerts on

GitHub's Dependabot vulnerability **alerts** are a repo-level setting, independent of who raises
update PRs. Renovate handling updates does not disable them — leave them enabled for the native
advisory surface.
