---
id: 11
slug: multiple-templates
status: draft
branch:
created: 2026-11-06T20:59:46-08:00
concluded:
pr:
---

# Ship multiple templates: python-package, bash, and python-workspace

## Plan

### Goal

Turn the single `template/` scaffold into a small set of templates, chosen at init
time:

| Template | What it is | Model |
|---|---|---|
| `python-package` | today's template: a uv package with ruff, pyrefly, pytest, pre-commit, CI, planners, and stanza | `template/` as it stands |
| `bash` | a shell CLI, with no Python packaging | [stanza](https://github.com/gitronald/stanza)'s layout |
| `python-workspace` | a uv workspace: a root `pyproject.toml` with `[tool.uv.workspace]` and member packages | the workspace repos in the fleet |

Depends on plan 010. The rename sets the names, the stamp table, and the script
names this plan builds on.

### The bash template, after stanza

stanza is a bash tool released with stanza itself. The parts to carry over:

- `VERSION` as the only version source, which stanza already reads and bumps
- `bin/<name>` as the entry point, `lib/<name>-*` for sourced modules, and
  optional `completions/`
- `install.sh` / `uninstall.sh`
- `tests/run.sh` running `tests/test-*.sh`, with a `.shellcheckrc`
- CI: `shellcheck` plus the test runner on Linux and macOS; a release-asset
  workflow instead of a PyPI publish
- the same planners, `.claude/`, `CHANGELOG.md`, and `.gitattributes` setup as
  every other template, with a Stop hook that runs `shellcheck` and the tests in
  place of ruff and pyrefly

### The python-workspace template

uv workspaces are already in use: searching the clones for `[tool.uv.workspace]`
on 2026-11-06 found three repos, and plan 008 fixed four workspace problems (the
hook root, pyrefly, ruff, worktrees) found while upgrading one of them. Look at
those repos for the shape, and copy none of their content.

- The root `pyproject.toml` holds `[tool.uv.workspace] members = ["packages/*"]`,
  `[tool.uv.sources]` with `workspace = true` entries, and the shared ruff,
  pyrefly, and pytest config.
- One member package is scaffolded under `packages/<name>/` with its own
  `pyproject.toml`, `src/`, and `tests/`.
- One `uv.lock` at the root; CI runs from the root with `uv sync --all-packages`.
- Decision to make (question 2): whether the root is an unbuilt shell or a
  package of its own.

### Layout

```
templates/
  _common/             # shared by every template: .claude/, .planners/, CHANGELOG.md,
                       # .gitattributes, and the shared parts of .github/
  python-package/      # today's template/, minus what moved to _common/
  bash/
  python-workspace/
```

Init copies `_common/` and then the chosen template over it, so a template's
file replaces the shared one at the same path. Three full copies would drift
apart; a shared layer keeps a fix to `.claude/` or the planners setup in one
place. Anything that differs by language (Stop hook, pre-commit config, CI
workflow, `.gitignore`) lives in each template.

### Init and upgrade

- `--template <name>` on the init script, defaulting to `python-package`, so
  current calls work unchanged.
- The stamp records the template as well as the release, e.g.
  `template = "python-package"`, `version = "X.Y.Z"`. Where the bash template
  keeps its stamp is question 1.
- `install-template` reads the stamp to pick the template for upgrade mode. A
  repo with no `template` key is `python-package`.
- `test-proj-init` and `tests/proj-init.test.sh` scaffold and check every
  template; CI runs the suite once per template.

### Order

a. Move `template/` to `templates/python-package/` and extract `_common/`, with
   no change to the output: the scaffold made before and after must be identical
   apart from the stamp.
b. Add `--template`, and teach the tests and CI to run once per template.
c. Add `python-workspace`, the smaller step, which reuses the Python tooling.
d. Add `bash`.
e. Update `install-template` (pick the template from the stamp), the README, and
   `docs/guides/`.
f. Minor release.

Steps c and d are independent. If this plan grows past ~500 lines, split them
into nested subplans.

### Open questions

1. Where does the bash template's stamp go, with no `pyproject.toml`? Options: a
   top-level `.repotemplates.toml` for bash only, or the same file for every
   template (which moves the Python stamp a second time, right after plan 010).
2. Is the python-workspace root a package of its own or an unbuilt shell? Both
   forms exist in the fleet.
3. Do the bash template's tests use a homegrown runner like stanza's, or bats?
4. Should a later template (a static site, a data-analysis repo) be in scope, or
   wait until these three are in use?
