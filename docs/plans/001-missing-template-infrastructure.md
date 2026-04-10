---
status: done
branch: claude/missing-template-infrastructure-MKZP2
created: 2026-04-10T16:01:30-07:00
completed: 2026-04-10T16:09:43-07:00
pr: https://github.com/gitronald/proj-template/pull/6
---

# Add missing template infrastructure

Add CI publishing, dependabot, issue/PR templates, changelog, and py.typed marker to the project template.

## Plan

### Current state

Branch `claude/missing-template-infrastructure-MKZP2` has 3 commits adding 8 new files:

- `template/.github/workflows/publish.yml` — PyPI publish workflow using trusted publishers (OIDC)
- `template/.github/dependabot.yml` — Dependabot config for github-actions and pip
- `template/.github/ISSUE_TEMPLATE/bug_report.yml` — Bug report issue template
- `template/.github/ISSUE_TEMPLATE/feature_request.yml` — Feature request issue template
- `template/.github/pull_request_template.md` — PR template
- `template/CHANGELOG.md` — Keep a Changelog template
- `template/PACKAGE/py.typed` — PEP 561 marker
- `docs/guides/trusted-publishers.md` — Setup guide for trusted publishers

### Fixes needed

1. **`dependabot.yml`: change ecosystem from `pip` to `uv`** — Dependabot has supported `package-ecosystem: uv` since March 2025. Using `pip` means it won't regenerate `uv.lock`, leaving the lockfile out of sync on every Dependabot PR.

2. **`publish.yml`: move permissions to job level and add `contents: read`** — `id-token: write` is currently at workflow level (too broad). Missing `contents: read` means `actions/checkout` will fail on private repos because explicitly setting any permission drops all others to `none`.

3. **`publish.yml`: update `setup-uv@v7` to `@v8.0.0`** — `astral-sh/setup-uv` stopped publishing floating major tags at v8. The `@v7` tag is frozen and will never be updated.

4. **`publish.yml`: split build and publish into separate jobs** — pypa docs recommend a `build` job (no elevated permissions) and a `publish` job (with OIDC token) so build-phase scripts can't access the token.

## Log

- 2026-04-10: Branch arrived with 3 commits adding 8 template files (publish workflow, dependabot, issue/PR templates, changelog, py.typed, trusted publishers guide)
- 2026-04-10: Code review identified 4 fixes needed (dependabot ecosystem, publish.yml permissions, setup-uv version, build/publish job separation); changelog empty sections confirmed intentional for a template
- 2026-04-10: Implemented all 4 fixes plus updated setup-uv in test.yml; confirmed `@v8` floating tag doesn't exist, pinned to `@v8.0.0`
- 2026-04-10: Validated all YAML files, opened PR #6

## Retrospective

- The original branch was generated externally and needed review before merging — catching issues early avoided shipping broken dependabot PRs and a publish workflow that would fail on private repos
- `astral-sh/setup-uv` dropping floating major tags at v8 was a non-obvious breaking change worth verifying — the reviewer flagged it at 85% confidence, and it turned out to be correct
- Fixing `test.yml` alongside `publish.yml` for the setup-uv bump was the right call since both files had the same stale reference
- Template files can't be functionally tested in the template repo itself — YAML validation is the practical ceiling
