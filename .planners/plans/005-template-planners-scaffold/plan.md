---
id: 5
slug: template-planners-scaffold
status: done
branch: feature/template-planners-scaffold
created: 2026-06-10T09:36:40-07:00
concluded: 2026-06-10T11:04:35-07:00
pr: https://github.com/gitronald/proj-template/pull/23
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

## Log

**2026-06-10 — implementation.**

- `62d2a06` replace template docs layout with planners — deleted
  `template/docs/` and `template/TODO.md`; added `template/.planners/`
  (empty index + `plans/.gitkeep`); appended the global-mode
  `planners-validate` hook block to `template/.pre-commit-config.yaml`;
  updated the root README tree.
- Verified by simulating the `proj-init.sh` pipeline (rsync + `PACKAGE`
  rename/replace) in a temp dir: `.planners/` survives intact, the stamped
  index is byte-identical to a fresh `planners index .` render, the hook
  YAML parses, and no stale `docs/`/`TODO.md` references remain.
- **Review follow-up:** review posted to the PR — one minor finding:
  the template `.gitignore` did not ignore `.worktrees/`, so every
  scaffolded repo would get a lazy-append noise commit on its first
  `/planners implement`. Actioned in `be15d66`. Check gate: no root test
  suite (non-uv root); `planners validate` ok (6 plans).

## Retrospective

- The global-mode decision did the heavy lifting: pre-PyPI, a per-repo
  dev dependency was impractical, and global mode reduced the scaffold to
  two static files plus a hook block — no holder, rule, or dependency to
  stamp.
- Stamping the generated empty index byte-identical to the CLI's render
  keeps `planners index .` a no-op on fresh repos; worth re-checking if
  the index format ever changes upstream.
- Simulating the scaffold pipeline in a temp dir was cheap and caught the
  questions that mattered (dotdir rsync, placeholder substitution) without
  needing a network clone.
