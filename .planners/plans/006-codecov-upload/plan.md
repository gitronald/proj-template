---
id: 6
slug: codecov-upload
status: inactive
branch:
created: 2026-09-05T21:54:21-07:00
concluded:
pr:
---

# Consider uploading coverage to Codecov from the template test workflow

## Plan

Parked follow-up to the coverage work that landed on 2026-09-05 (`addopts = "--cov"`,
`[tool.coverage]` with `fail_under = 50`, and a CLI smoke test in the scaffold). That work
makes coverage a local and CI gate, but the report only ever lands in the job log. This
plan evaluates whether the template should also publish coverage to an external service so
projects get history, PR diffs, and a README badge.

### Why it was deferred

- No repo scaffolded from the template uploads coverage today, so there is no house
  convention to encode yet.
- Codecov needs a per-repo token (or the Codecov GitHub App installed on the account),
  which is a post-scaffold enrollment step rather than something `proj-init.sh` can do
  unattended. That is the same shape as Renovate, which got its own
  `install-renovatabot` skill for the secrets half.
- The `fail_under` floor already gives CI a hard signal without any third party.

### Options to weigh

1. **Codecov via `codecov/codecov-action`** — the common default. Needs `CODECOV_TOKEN` as
   a repo secret for private repos, or the App for public ones. Gives PR comments with
   coverage diffs and a badge. Adds a third-party action to every child repo's workflow, so
   pin it by SHA and route its updates through the existing Renovate config.
2. **Coveralls** — similar tradeoffs, smaller ecosystem.
3. **No third party** — keep `term-missing` output, optionally add `--cov-report=xml` and
   upload the XML as a workflow artifact so it is retrievable without an external service.
   Cheapest and keeps the trust boundary in-house, but no badge or PR diff.

### If option 1 is chosen

- Add a guarded upload step to `template/.github/workflows/test.yml`, running only on one
  matrix cell (the pinned `UV_PYTHON`) and only when the token secret is present, so a fresh
  scaffold without enrollment does not fail CI.
- Emit `--cov-report=xml` in `addopts` alongside `term-missing`.
- Add a `codecov.yml` to the template payload with a `patch` and `project` target that
  matches the `fail_under` floor, so the two gates cannot disagree.
- Extend the `install-template` sync matrix and the `github-automation` guide.
- Add an enrollment skill (or fold into `install-renovatabot`) that sets the secret from a
  local `.env` and installs the badge line in the README.

### Open questions

- Is the badge worth a third-party action in every child repo, given the floor already
  gates CI?
- Public vs. private repos differ in token handling; the template serves both.
