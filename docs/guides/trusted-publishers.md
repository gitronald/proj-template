# Trusted Publishers

Projects created from this template include a [publish workflow](../../template/.github/workflows/publish.yml) that uploads packages to PyPI using [Trusted Publishers](https://docs.pypi.org/trusted-publishers/). This replaces manual API tokens with OpenID Connect (OIDC) — GitHub proves the publish came from your repo, and PyPI accepts it without stored secrets.

## How it works

When you push a tag matching `v*`, the publish workflow runs two jobs:

1. **Build** — checks out the code, builds the package with `uv build`, and uploads the dist artifacts
2. **Publish** — downloads the artifacts and publishes to PyPI via `pypa/gh-action-pypi-publish`

Separating build and publish ensures the build job has no access to the OIDC token. Authentication happens automatically through OIDC in the publish job — its `id-token: write` permission lets GitHub mint a short-lived token that PyPI verifies against your trusted publisher configuration.

## Setup

The publish workflow is **disabled by default**: tag pushes trigger it, but both
jobs skip until you opt in. Three things need to be configured: enabling the
workflow, a GitHub environment, and a PyPI trusted publisher.

### 1. Enable the workflow

Set the `PUBLISH_ENABLED` repository variable to `true`:

```bash
gh variable set PUBLISH_ENABLED --body true
```

To pause publishing again, set it to `false` or delete it
(`gh variable delete PUBLISH_ENABLED`). You can also manage it under
**Settings > Secrets and variables > Actions > Variables**.

### 2. Create a GitHub environment

1. Go to your repo's **Settings > Environments**
2. Click **New environment**
3. Name it `pypi` (must match the `environment:` value in the workflow)
4. Optionally add deployment protection rules (e.g., require approval before publish)

### 3. Configure PyPI

#### For a new package (not yet on PyPI)

1. Go to https://pypi.org/manage/account/publishing/
2. Under **Add a new pending publisher**, fill in:
   - **PyPI project name**: your package name (from `pyproject.toml`)
   - **Owner**: your GitHub username or org
   - **Repository name**: your GitHub repo name
   - **Workflow name**: `publish.yml`
   - **Environment name**: `pypi`
3. Click **Add**

The first publish from your workflow will automatically create the project on PyPI.

#### For an existing package (already on PyPI)

1. Go to `https://pypi.org/manage/project/<your-package>/settings/publishing/`
2. Under **Add a new publisher**, fill in the same fields as above
3. Click **Add**

### 4. Publish a release

```bash
stanza release patch   # bumps version, commits, tags, pushes
```

The `v*` tag push triggers the workflow. Check the **Actions** tab in your repo to confirm the publish succeeded.

## Troubleshooting

**"Token request failed"** — The `id-token: write` permission is missing or the workflow is running in a context that doesn't support OIDC (e.g., a fork PR). Check that the permission is set at the job or workflow level.

**"Publisher not configured"** — The owner, repo, workflow filename, or environment name on PyPI doesn't match your GitHub setup. All four fields must match exactly.

**"Environment not found"** — The `pypi` environment hasn't been created in your repo's settings. See step 2 above.

**Workflow ran but nothing published (jobs skipped)** — `PUBLISH_ENABLED` is not set to `true`. See step 1 above.

## TestPyPI

To test publishing without affecting the real index, add a separate workflow or modify `publish.yml` temporarily:

```yaml
- uses: pypa/gh-action-pypi-publish@release/v1
  with:
    repository-url: https://test.pypi.org/legacy/
```

Configure a matching trusted publisher on [TestPyPI](https://test.pypi.org/manage/account/publishing/) with environment name `testpypi`.
