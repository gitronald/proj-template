---
id: 4
slug: migrate-to-planners-layout
status: active
branch: feature/migrate-to-planners-layout
created: 2026-06-10T09:35:21-07:00
concluded:
pr:
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
