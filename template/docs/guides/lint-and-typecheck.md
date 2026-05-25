# Lint and type-check

Projects created from this template ship with two code-quality tools:
[ruff](https://docs.astral.sh/ruff/) for formatting and linting, and
[pyrefly](https://pyrefly.org/) for type checking. They run at three points:

- **commit time** — pre-commit hooks (see [`pre-commit.md`](pre-commit.md)),
- **push / PR** — the GitHub Actions test matrix (Python 3.11–3.14),
- **agent task completion** — a Claude Code `Stop` hook (see [Agentic use](#agentic-use)).

ruff and pyrefly divide the work: ruff owns *style and lint* (layout, imports,
modern idioms, common bugs), pyrefly owns *types* (annotations, type mismatches,
undefined names). Run both from the project root:

```bash
uv run ruff format .       # auto-format
uv run ruff check --fix .  # lint and auto-fix
uv run pyrefly check       # type check
```

## ruff

Ruff settings live in `pyproject.toml` under `[tool.ruff]` and
`[tool.ruff.lint]`. The template enables these rule sets via `select`:

- **F** — pyflakes
- **E** — pycodestyle errors
- **W** — pycodestyle warnings
- **I** — isort (import sorting)
- **UP** — pyupgrade (modern Python idioms)

`ruff format` rewrites layout; `ruff check` enforces the rules and, with
`--fix`, auto-applies the mechanical ones (import sorting, many `UP`
modernizations). Logic findings (most `F` rules) need a real edit.

To broaden coverage, add rule codes to `select` — for example `B`
(flake8-bugbear) or `SIM` (flake8-simplify). See the
[ruff rules reference](https://docs.astral.sh/ruff/rules/) for the full list.

**Keep ruff versions in step.** Ruff appears in two places: the `rev` in
`.pre-commit-config.yaml` (used by the commit-time hook) and the `ruff>=` floor
in `pyproject.toml` (used by `uv run ruff` in CI and the Stop hook). When you
bump one, bump the other to the same release so commit-time and CI behavior
match. `uv run pre-commit autoupdate` updates the `rev`; update the floor by
hand.

## pyrefly

pyrefly is Meta's Python type checker. Its config lives in `pyproject.toml`
under `[tool.pyrefly]` (keys are hyphenated: `python-version`,
`project-includes`, `project-excludes`, `preset`).

### Presets

pyrefly bundles named presets that switch groups of error kinds on or off, from
weakest to strongest:

| Preset    | Use |
|-----------|-----|
| `off`     | No checking. |
| `basic`   | Auto-applied only to projects with *no* pyrefly config at all. |
| `legacy`  | Lenient; eases migration from other checkers. |
| `default` | Applied when a `[tool.pyrefly]` section exists without a `preset`. |
| `strict`  | Strongest — adds checks on top of `default` and flags implicit `Any`. |

**This template uses `strict`.** A scaffolded project starts with good typing
hygiene rather than drifting into untyped code. (Because the template has always
had a `[tool.pyrefly]` section, the effective baseline before this was
`default`, not `basic` — so adopting `strict` is a step up from `default`.)

`python-version` is pinned to `3.11`, the floor of `requires-python`, so pyrefly
checks compatibility against the lowest supported interpreter regardless of the
`3.14` development interpreter.

### Core CLI

```bash
uv run pyrefly check                    # type-check the project
uv run pyrefly init                     # migrate a mypy/pyright config in
uv run pyrefly suppress                 # insert inline ignore comments
uv run pyrefly infer                    # infer and write annotations
uv run pyrefly coverage report          # JSON type-coverage report
```

Note the coverage subcommand is `pyrefly coverage report`, not `pyrefly
report`.

### Baseline files (incremental adoption)

For a codebase that can't go clean immediately, record the current errors as an
accepted baseline so CI only fails on *new* ones:

```bash
uv run pyrefly check --baseline=pyrefly-baseline.json   # check against baseline
uv run pyrefly check --update-baseline                  # refresh the baseline
```

You can also set `baseline = "pyrefly-baseline.json"` in `[tool.pyrefly]`. Burn
the baseline down over time; in steady state, aim for an empty baseline and a
clean `strict` run.

### Versioning caveat

pyrefly does **not** follow strict semver — any release, even a patch, may
introduce new error kinds or behavior changes. Two consequences:

- The exact version is pinned by the committed `uv.lock` (created at scaffold
  time); the `pyrefly>=1.0.0` floor only keeps new projects on the stable line.
- **Do not blind-auto-merge pyrefly bumps.** `dependabot.yml` proposes weekly
  `uv` updates, and a pyrefly bump can turn CI red on previously-clean code.
  Review pyrefly PRs deliberately: read the changelog, run the checks locally,
  and fix or suppress any new errors before merging.

## Typing your tests

`project-includes = ["."]` pulls `tests/` into type checking, so test code is
checked for imports, undefined names, and type mismatches like any other module.
But a per-glob override relaxes one check there:

```toml
[[tool.pyrefly.sub-config]]
matches = "tests/**"

[tool.pyrefly.sub-config.errors]
implicit-any = false
```

This disables only `implicit-any` under `tests/`, so unannotated pytest fixture
parameters (`def test_x(tmp_path):`) don't force annotations — a friction every
project hits on its first fixture-using test. Everything else stays checked.

Annotating fixture params is still encouraged where it's cheap — it improves
editor completion and catches misuse. Common fixture types:

| Fixture            | Annotation |
|--------------------|------------|
| `tmp_path`         | `Path` |
| `tmp_path_factory` | `pytest.TempPathFactory` |
| `monkeypatch`      | `pytest.MonkeyPatch` |
| `capsys`           | `pytest.CaptureFixture[str]` |
| `caplog`           | `pytest.LogCaptureFixture` |
| `request`          | `pytest.FixtureRequest` |

**Tightening to fully-typed tests later.** To enforce annotations in tests too,
remove the `tests/**` sub-config (or set `implicit-any = true`). Defer this until
typed-test friction is clearly worth it — for example, a recurring type bug in
test code, or a test suite that has grown substantial. Treat it as a deliberate,
documented tightening rather than a silent flip.

## Agentic use

In-editor agents can finish a task with lint or type errors still present. Two
mechanisms close that gap, following pyrefly's
[agentic-loop guidance](https://pyrefly.org/blog/pyrefly-agentic-loop/) (which
notes a skill alone is not enough):

- **`CLAUDE.md` directive** — a "Before finishing a task" instruction tells the
  agent to run `uv run ruff check .` and `uv run pyrefly check` and fix all
  reported errors before completing work.
- **`Stop` hook** — `.claude/hooks/lint-typecheck.sh` runs both checks
  (non-mutating) when the agent tries to stop. If either fails, it exits 2,
  which feeds the errors back to the agent and keeps the conversation going so
  it fixes them. Configured in `.claude/settings.json`.

The `lint-and-typecheck` skill (`.claude/skills/`) codifies the same workflow
for on-demand use — running format/fix/check and interpreting pyrefly's output.

## Migrating an existing project

To bring this tooling to a project that wasn't scaffolded from the template:

1. Copy `[tool.ruff]`, `[tool.ruff.lint]`, and `[tool.pyrefly]` from this
   template's `pyproject.toml`, plus the `pyrefly` and `ruff` dev dependencies.
2. Run `uv run pyrefly init` to auto-migrate an existing mypy or pyright config
   into `[tool.pyrefly]`.
3. If `strict` surfaces many errors, stage adoption: `uv run pyrefly suppress`
   to insert inline ignores, and/or `--baseline` to accept the current error set
   and fail only on new ones. Burn it down over time.
4. Copy the pre-commit hooks, the CI workflow steps, and (for Claude Code
   projects) the `.claude/` hook, settings, and skill.
