---
id: 5
slug: template-planners-scaffold
status: draft
branch:
created: 2026-06-10T09:36:40-07:00
concluded:
pr:
---

# Update template scaffold to the planners layout

## Plan

Surfaced by the planners migration (plan 004). The `template/` scaffold
still stamps new projects with the legacy layout: `TODO.md`, `docs/plans/`,
and the boilerplate `docs/README.md` plans-pointer. Update the scaffold to
the `.planners/` model (planners holder, `.planners/plans/`, validate hook
in the generated `.pre-commit-config.yaml`), and refresh the root README's
generated-tree diagram to match. Left untouched by plan 004 since scaffold
content is template product design, not this repo's own plan system.
