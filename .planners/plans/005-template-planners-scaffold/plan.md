---
id: 5
slug: template-planners-scaffold
status: active
branch: feature/template-planners-scaffold
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

### Design

Remove `docs/` from the template entirely — the lint-and-typecheck guide
already moved to a machine-global skill, leaving only boilerplate — and
stamp the `.planners/` layout instead.

Mode decision: **global**. The planners package is pre-PyPI, so a per-repo
`uv add --dev planners` dependency isn't practical; the fleet runs
`planners install --global` (one CLI + holder/rule per machine, under
`~/.claude/`). A scaffolded repo therefore needs no holder, no rule, and no
dependency — only the static layout and the hook block, the same shape this
repo itself uses.

Changes, all in `template/` unless noted:

1. **Delete** `docs/` (`README.md`, `guides/.gitkeep`, `plans/.gitkeep`)
   and `TODO.md`.
2. **Add** `.planners/README.md` — the canonical empty index exactly as
   `planners index .` renders it (`# Plans` + empty table header), so the
   stamped file matches what the CLI regenerates — and
   `.planners/plans/.gitkeep` (the CLI creates `plans/` lazily on first
   `add`; the `.gitkeep` keeps it present from the initial commit).
3. **Append** the `planners-validate` hook block to
   `.pre-commit-config.yaml` with the global-mode entry
   (`entry: planners validate`, `language: system`,
   `files: ^\.planners/plans/[^/]+/plan\.md$`). With no planners CLI on a
   machine, the hook only fires when a plan file is staged, so the scaffold
   stays usable for non-fleet users.
4. **Root `README.md`** (this repo): update the template-structure tree —
   drop `docs/` and `TODO.md`, add `.planners/`.

`proj-init.sh` needs no changes: `rsync -a` already copies dotdirs, the
empty index contains no `PACKAGE` placeholder, and `git add -A` commits
`.planners/` in the initial commit.
