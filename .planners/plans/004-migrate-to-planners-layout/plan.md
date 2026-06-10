---
id: 4
slug: migrate-to-planners-layout
status: done
branch: feature/migrate-to-planners-layout
created: 2026-06-10T09:35:21-07:00
concluded: 2026-06-10T09:36:42-07:00
pr: https://github.com/gitronald/proj-template/pull/22
---

# Migrate plans to the .planners layout

## Plan

Migrate this repo from the legacy `docs/plans/` + `TODO.md` layout to the
`planners` package's `.planners/` layout, following the fleet rollout runbook
(quipus plan 033, `planners-migration` skill).

Scope:

- Standardize frontmatter on all 4 legacy plans (000-003): add `id`/`slug`
  and rename the terminal field `completed` -> `concluded`. All are done
  with branch + PR filled.
- Move each plan to `.planners/plans/<NNN>-<slug>/plan.md` and repoint any
  in-repo references to the old paths.
- Retire `TODO.md` — every item links a plan; no open items.
- No `docs/README.md` exists — nothing to restore (`docs/guides/` stays).
- Install the planners holder and wire the pre-commit config. **Non-uv
  root** (the uv project lives in `template/`): the hook config is written
  but stays dormant; `planners validate`/`index` run via the global CLI.

## Log
**2026-06-10 — migration run (review list + decisions).**

- **Frontmatter pass (4 legacy plans, 000-003):** added `id`/`slug`; renamed
  `completed:` -> `concluded:`. All done with branch + PR filled.
- **TODO.md retired with no stubs:** every item linked a done plan.
- **No docs/README.md existed** — nothing to restore.
- **Template scaffold deliberately untouched:** `template/` still stamps the
  legacy layout (TODO.md, docs/plans/, boilerplate docs/README.md) and the
  root README's tree diagram reflects it. Updating the scaffold to the
  `.planners/` model is product design work — captured as draft stub plan
  005 (template-planners-scaffold), not smuggled into this migration.
- **Hook (non-uv root):** the uv project lives in `template/`; the
  planners-validate config is wired but dormant. `planners
  validate`/`index` run via the global CLI.
- **Review follow-up:** review posted to PR #22 — no findings. Check gate:
  no root test suite; `planners validate` ok (6 plans).

## Retrospective

- A template repo migrates on two planes: its own plan system (this plan)
  and the scaffold it stamps (plan 005). Keeping them separate keeps the
  migration mechanical and gives the scaffold change its own review.
