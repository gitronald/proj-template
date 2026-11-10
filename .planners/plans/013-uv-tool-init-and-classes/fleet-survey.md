# Fleet survey for question 5

Taken 2026-11-09 over the 27 repos that `repotemplates check --repos-dir`
reports as stamped, all on template 0.11.7. Each candidate file was rendered
from every release tag (placeholders filled from the repo's `project.name`) and
compared byte for byte. "current" means it equals HEAD's template, "matches"
means it equals an earlier release, and "one-off" means it equals none.

| File | current | matches | one-off | absent | What the one-offs are |
|---|---|---|---|---|---|
| `.pre-commit-config.yaml` | 22 | 0 | 5 | 0 | 4 differ only in the ruff `rev:`, all newer than the template's; 1 is a true customization |
| `.github/workflows/test.yml` | 10 | 0 | 16 | 1 | Python matrix narrowed to the supported versions (13), newer `setup-uv` pin, extra setup steps (system packages, tool installs), and a few on the older single-Python shape |
| `.github/workflows/publish.yml` | 17 | 0 | 4 | 6 | 3 newer `setup-uv` pin, 1 with an environment URL; the 6 absent repos do not publish |
| `.github/dependabot.yml` | 0 | 25 | 0 | 2 | All 25 equal 0.11.7: 0.12.0 changed only the URL in a comment. 1 absent repo uses Renovate, and 1 has no `.github/` |
| `.github/renovate.json`, `workflows/renovate.yml` | 0 | 1 | 0 | 26 | Only the Renovate repo has them |
| `.gitignore` | 3 | 0 | 24 | 0 | 9 contain every template line and add local ones; 15 leave out `.claude/`, or spell it `.claude` or `.claude/*` |
| `.gitattributes` | 24 | 0 | 3 | 0 | All 3 contain every template line and add local ones |
| `.python-version` | 25 | 0 | 2 | 0 | 2 pin a patch release (`3.14.x`) |
| `.claude/CLAUDE.md` | 2 | 0 | 25 | 0 | Project prose: not template-owned |

`pyproject.toml` tool tables: all 27 have the template's ruff `select` and
pyrefly `preset = "strict"`. `target-version` varies with `requires-python`.

Pin direction: every pin difference is the repo ahead (`setup-uv` v10.3.3 and
`ruff-pre-commit` v0.17.3 in repos, against v10.3.0 and v0.17.1 in
`template/`). Dependabot bumps the consumers, and nothing bumps the template
(step f).
