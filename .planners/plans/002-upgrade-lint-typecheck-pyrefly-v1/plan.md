---
id: 2
slug: upgrade-lint-typecheck-pyrefly-v1
status: done
branch: feature/upgrade-lint-typecheck
created: 2026-05-25T13:10:08-07:00
concluded: 2026-05-25T14:30:43-07:00
pr: https://github.com/gitronald/proj-template/pull/10
---

# Upgrade lint and type-check tooling for pyrefly v1.0 with agentic integration

## Context

Two upstream releases prompt this update:

- **pyrefly v1.0.0** (May 2026) — the first stable release of Meta's Python type checker. It is now production-ready (default on Instagram, adopted by PyTorch/NumPy/pandas-stubs/JAX), reaches >90% conformance with the typing spec (up from 70% at beta), and ships materially fewer false positives. v1.0 also introduces **named config presets**, **coverage reporting**, and **baseline files**, plus published guidance for using pyrefly inside agentic coding loops.
- **ruff** — the template pins `ruff-pre-commit` at `v0.15.5`; latest is `v0.15.14`. This is a routine within-`0.15.x` patch bump (bug fixes, rule/stub updates), not a behavior overhaul.

The template currently wires both tools through pre-commit and CI but has **no agentic integration** — nothing makes an in-editor agent run the checks before finishing a task. The pyrefly team's [agentic-loop guidance](https://pyrefly.org/blog/pyrefly-agentic-loop/) recommends closing that gap with a `Stop` hook plus an `AGENTS.md`/`CLAUDE.md` directive (noting a skill alone is insufficient).

### Current template state (baseline)

- `template/pyproject.toml`
  - dev group: `pyrefly` and `ruff` are **unpinned**.
  - `[tool.ruff.lint]` selects `F, E, W, I, UP`; `target-version = "py311"`.
  - `[tool.pyrefly]`: `python-version = "3.11"`, `project-includes = ["."]` — **no preset set**. Because the section *exists*, pyrefly v1.0 applies the **`default`** preset (the `basic` preset only auto-applies to projects with *no* pyrefly config at all). So the real change this plan makes is **`default` → `strict`**, not `basic` → `strict`.
- `template/.pre-commit-config.yaml` — `ruff-pre-commit` at `v0.15.5` (ruff-format + ruff `--fix`); a local `pyrefly-check` hook running `uv run pyrefly check`.
- `template/.github/workflows/test.yml` — runs `ruff check`, `ruff format --check`, `pyrefly check`, `pytest` across Python 3.11–3.14.
- `template/.claude/settings.local.json` — permissions only; **no hooks**.
- `template/CLAUDE.md` — Development section mentions lint/type-check via pre-commit, but no directive to run them before completing a task.
- `proj-init.sh` copies all of `template/` via `rsync -a` (including `.claude/`), so any new file added under `template/` automatically ships to scaffolded projects.
- Root `docs/guides/` holds the template's own reference guides (`pre-commit.md`, `trusted-publishers.md`); `template/docs/guides/` is empty (`.gitkeep`).

### Decisions (confirmed with user)

- **Preset: `strict`** — the template should model good typing hygiene; strict adds checks on top of default and discourages `Any`.
- **Agentic integration: hook + directive + skill** — committed `Stop` hook, a `CLAUDE.md`/`AGENTS.md` directive, and a reusable skill that codifies the lint/type-check workflow.

## Plan

### 1. Version bumps

- `template/.pre-commit-config.yaml`: bump `astral-sh/ruff-pre-commit` `rev` from `v0.15.5` to `v0.15.14`.
- `template/pyproject.toml` dev group: pin floors so scaffolded projects resolve the intended majors —
  - `pyrefly>=1.0.0` (was bare `pyrefly`; pre-1.0 alpha/beta resolutions are no longer desirable).
  - `ruff>=0.15` (was bare `ruff`).
  - **Rationale for pinning pyrefly:** pyrefly explicitly does **not** follow strict semver — any release (minor or patch) may introduce new type errors or breaking changes. A floor of `>=1.0.0` keeps new projects on the stable line; the committed `uv.lock` (created at scaffold time) pins the exact version for reproducibility.

### 2. Adopt pyrefly v1.0 config in `template/pyproject.toml`

Update `[tool.pyrefly]`:

```toml
[tool.pyrefly]
preset = "strict"
python-version = "3.11"
project-includes = ["."]
project-excludes = ["**/__pycache__", "**/.venv"]

# tests/ stays type-checked (imports, undefined names, type mismatches),
# but the implicit-Any check is relaxed there so unannotated pytest fixture
# params (e.g. `def test_x(tmp_path):`) don't force annotations. See §5.
[[tool.pyrefly.sub-config]]
matches = "tests/**"

[tool.pyrefly.sub-config.errors]
implicit-any = false
```

- `preset = "strict"` is the headline change — opts new projects into the strictest checking by default.
- Keep `python-version = "3.11"` (the floor of `requires-python = ">=3.11"`) so pyrefly checks compatibility against the lowest supported interpreter, independent of the `3.14` dev `.python-version`.
- Add `project-excludes` for `__pycache__`/`.venv` hygiene (v1.0 config key).
- The `[[tool.pyrefly.sub-config]]` block applies a per-glob override to `tests/**`, disabling the `implicit-any` error kind there (Option C — see §5). Tests stay checked for imports, undefined names, and type mismatches; only the fixture-parameter annotation tax is lifted. Smoke-test the sub-config behaves as expected during implementation (pyrefly sub-configs are relatively new).
- Note: v1.0 config keys are hyphenated (`python-version`, `project-includes`, `project-excludes`, `preset`). Verify against `pyrefly init` output during implementation since the template hand-maintains this block rather than generating it.

### 3. Agentic integration

**3a. Committed Stop hook** — add `template/.claude/settings.json` (a new, shared, committed file — distinct from the existing `settings.local.json` which stays for personal permissions) with a `Stop` hook that runs the checks and surfaces failures back to the agent.

Confirmed against current Claude Code docs (https://code.claude.com/docs/en/hooks):
- The `Stop` event takes a **flat array of command objects** — it does **not** use a `matcher`, and there is **no** nested `{ "hooks": [...] }` wrapper (that wrapper is only for matcher-based events like `PreToolUse`). A `matcher` field on `Stop` is silently ignored.
- For a `Stop` hook, **exit code 2** "prevents Claude from stopping and continues the conversation," and **stderr is fed back to Claude** as the message. That is exactly the desired behavior: on a lint/type failure, the agent keeps going and sees the errors to fix.

Rather than embed shell logic in a JSON string (fragile escaping; `exit 2` precedence across `&&`/`||`), ship a small wrapper script `template/.claude/hooks/lint-typecheck.sh` (copied to scaffolded projects via `rsync`, alongside `settings.json`) that runs both tools non-mutatingly and exits 2 if **either** fails:

```bash
#!/bin/bash
# Lint + type-check gate for the Claude Code Stop hook.
# Runs ruff (lint only, no formatting/mutation) and pyrefly; exits 2 with
# stderr output if either fails, so the agent sees the errors and continues.
set -u
fail=0
uv run ruff check . >&2 || fail=1
uv run pyrefly check >&2 || fail=1
[ "$fail" -eq 0 ] || exit 2
```

`settings.json` then just points at the script:

```json
{
  "hooks": {
    "Stop": [
      {
        "type": "command",
        "command": ".claude/hooks/lint-typecheck.sh",
        "timeout": 120
      }
    ]
  }
}
```

- Use `ruff check` (lint, non-mutating), **not** `ruff format` — auto-formatting/mutation stays in pre-commit; the Stop hook only *reports*.
- `timeout: 120` (not 60): the first run after a fresh scaffold may resolve/download the uv environment, which can exceed 60s.
- `chmod +x` the script so it ships executable.

**3b. Directive in `template/CLAUDE.md`** — add an explicit instruction under Development (and/or a top-level "Before finishing" line) mandating: run `uv run ruff check .` and `uv run pyrefly check` at the project root and fix all reported errors before completing a task. Per pyrefly's guidance this directive is the reliable backstop that a skill alone does not provide. Consider whether scaffolded projects should also get an `AGENTS.md` for editor-agnostic agents (decide during implementation — `CLAUDE.md` is the minimum).

**3c. Reusable skill** — add a skill that codifies the lint + type-check workflow for on-demand invocation (e.g., `lint-and-typecheck`): run ruff format/fix + ruff check, run pyrefly check, interpret pyrefly's output, and apply v1.0 adoption tooling when relevant (`pyrefly suppress`, `pyrefly infer`, baseline files). Decide skill home during implementation: ship inside `template/.claude/skills/` so scaffolded projects inherit it, vs. a user-level skill in `~/.claude/skills/`. Default: ship in the template so the workflow travels with each project. Use `/skill-creator` to author it.

### 4. Guide doc — `template/docs/guides/lint-and-typecheck.md`

**Placement decision (revised after review):** ship the guide **inside the template** at `template/docs/guides/lint-and-typecheck.md`, not in the repo root `docs/guides/`. Rationale: the guide explains tooling that *lives in each scaffolded project* (the Stop hook, the `CLAUDE.md` directive, the skill, the pyrefly/ruff config), so it should travel with those projects — root `docs/guides/` never ships (`rsync` copies only `template/`). This also fulfills "complement a skill," since the skill (§3c) ships in the template too. Keep the same audience voice ("Projects created from this template include…"). (Note: the existing `pre-commit.md` / `trusted-publishers.md` live root-only and have this same gap — migrating them into `template/` is a reasonable follow-up but is **out of scope** here.)

One combined guide covering both tools, with these sections:

- **Overview** — ruff (format + lint) and pyrefly (type check) and how they divide responsibility; how they relate to pre-commit (commit-time), CI (push/PR), and the Stop hook (agent task completion).
- **ruff** — the selected rule sets (`F/E/W/I/UP`), `ruff check`/`ruff format`, `--fix`, and how to extend `select`.
- **pyrefly v1.0** — the preset model (`off`/`basic`/`legacy`/`default`/`strict`) and why the template uses `strict` (it was previously on `default`); core CLI (`pyrefly check`, `init`, `suppress`, `infer`, and `pyrefly coverage report` for JSON type-coverage — note: the command is `pyrefly coverage report`, not `pyrefly report`); baseline files for incremental adoption (`--baseline=<path>` / `--update-baseline`, or the `baseline = "..."` config key); and the **semver caveat** (any version may add errors — pin and upgrade deliberately).
- **Typing your tests** — explain that `tests/` is type-checked but `implicit-any` is relaxed there (Option C), so fixture params don't *require* annotations — but annotating them is encouraged and improves the editing experience. Include the fixture-type cheat-sheet: `tmp_path: Path`, `monkeypatch: pytest.MonkeyPatch`, `capsys: pytest.CaptureFixture[str]`, `caplog: pytest.LogCaptureFixture`, `request: pytest.FixtureRequest`, `tmp_path_factory: pytest.TempPathFactory`. Note the future option to tighten to fully-strict tests by removing the `tests/**` sub-config.
- **Agentic use** — what the Stop hook does and the `CLAUDE.md` directive, linking the [pyrefly agentic-loop post](https://pyrefly.org/blog/pyrefly-agentic-loop/) and the `lint-and-typecheck` skill.
- **Migrating an existing project** — `pyrefly init` to auto-migrate mypy/pyright config; `pyrefly suppress` + baseline to stage adoption.

Cross-link from the new project's `template/CLAUDE.md` Development section. (Note: both `docs/README.md` files just say "See `guides/`" without enumerating individual guides, so no index edit is needed there.)

### 5. CI alignment (`template/.github/workflows/test.yml`)

- CI already runs `ruff check`, `ruff format --check`, and `pyrefly check` — no structural change needed.
- Confirm the strict preset doesn't break the template's own placeholder package under CI. The current stub (`PACKAGE/cli.py` `hello() -> None` with no params; `tests/test_PACKAGE.py` `test_placeholder()` with no params) is annotated/parameter-free and should pass `strict` clean — `strict` enables `implicit-any-parameter` (fires on unannotated params) but neither stub function has parameters. Verify in practice.
- **`tests/` under strict — RESOLVED: Option C (relax `implicit-any` in `tests/` via sub-config).** `project-includes = ["."]` pulls `tests/` into checking, and `strict`'s `implicit-any` fires on the first pytest fixture parameter a developer adds without an annotation (e.g. `def test_x(tmp_path):`) — friction every scaffolded project would hit early. The options considered:
  - **A — keep `tests/` fully strict.** Maximal hygiene, but immediate red CI on the first fixture-using test; recurring annotation tax on `@parametrize` params and untyped third-party fixtures.
  - **B — exclude `tests/` entirely.** Zero friction, but blunt — loses cheap, valuable checks (imports, undefined names, type mismatches) in the code that exercises the API.
  - **C — check `tests/` but disable `implicit-any` there** (chosen). Keeps imports/undefined-names/type-mismatch checking; drops only the fixture-parameter annotation tax. A gradient instead of a cliff, at the cost of two extra config stanzas.

  Implemented via the `[[tool.pyrefly.sub-config]]` block in §2. Also annotate the shipped example test (`tests/test_PACKAGE.py`) to model good practice for the cases C doesn't force, and include the pytest fixture-type cheat-sheet (`tmp_path: Path`, `monkeypatch: pytest.MonkeyPatch`, `capsys: pytest.CaptureFixture[str]`, `caplog: pytest.LogCaptureFixture`, `request: pytest.FixtureRequest`, `tmp_path_factory: pytest.TempPathFactory`) in the guide (§4).

  **Future path to A:** if the template later wants to enforce fully typed tests, advance C → A by removing the `tests/**` sub-config block (or flipping `implicit-any = true`). Defer until typed-test friction is clearly worth it (e.g., a recurring test-code type bug, or the project's tests grow substantial). Note this transition in the guide so it's a deliberate, documented step rather than a silent tightening.
- **Main risk:** `strict` on real scaffolded code surfaces more errors than the previous `default`; that is intended, but the friction (esp. tests) should be documented so it isn't surprising.

### 6. Verify

- Run `uv sync --all-groups` and `uv run pyrefly check` / `uv run ruff check .` against `template/` (or a throwaway scaffold via `proj-init.sh`) to confirm the strict preset and pinned versions resolve and pass.
- Confirm `pre-commit run --all-files` passes with the bumped ruff rev.
- Manually exercise the Stop hook (trigger a deliberate type error, confirm the agent sees the stderr/exit-2 failure).

## Implementation order

1. Version bumps (§1) — low risk, isolated.
2. pyrefly preset + config (§2), then verify the template stub passes `strict` (§5) — resolve any stub fixes here.
3. Stop hook + `settings.json` (§3a) and `CLAUDE.md` directive (§3b).
4. Skill (§3c) via `/skill-creator`.
5. Guide doc (§4).
6. Full verify (§6); update `CHANGELOG.md`; version bump via `stanza release`.

## Open questions / flagged areas

- ~~Exact Claude Code Stop-hook JSON schema~~ — **resolved** (flat array, no matcher/wrapper; exit 2 blocks stop and feeds stderr back). Shell fragility resolved via the wrapper script (§3a).
- ~~Confirm pyrefly v1.0 TOML key spellings~~ — **resolved**: hyphenated (`preset`, `python-version`, `project-includes`, `project-excludes`); same in `pyproject.toml` and `pyrefly.toml`. Still worth a sanity check against `pyrefly init` output during implementation.
- ~~`tests/` under `strict`~~ — **resolved: Option C** (sub-config disables `implicit-any` in `tests/`; keeps other checks). Future path to A documented (§5).
- Skill home: ship in `template/.claude/skills/` (travels with projects) vs. user-level (§3c). Leaning template.
- Whether to also add `AGENTS.md` for non-Claude agents (§3b).
- pyrefly pin: bare `>=1.0.0` floor vs. capped (`>=1.0,<1.1` / `<2`). Floor is acceptable since `uv.lock` is the real reproducibility guarantee (R8).

## Review findings (expert fleet)

Four reviewers (Claude Code hooks/skills, Python tooling fact-check, critical plan review, template-propagation) reviewed this plan. Findings, with the resulting changes already folded into the sections above:

**Resolved conflicts between reviewers:**
- **Stop-hook schema** — reviewers disagreed (flat array vs. nested `hooks` wrapper). Settled against the [current docs](https://code.claude.com/docs/en/hooks): **flat array, no matcher, no wrapper** for `Stop`. §3a corrected.
- **Will `settings.json` ship?** — one reviewer warned it would be git-ignored. The propagation reviewer empirically ran `git check-ignore` against the live global ignore (`~/.config/git/ignore`), which targets only `**/.claude/settings.local.json` — so a new `.claude/settings.json` and `.claude/skills/` are **not** ignored and will track/clone/rsync fine. No new `.gitignore` negation needed; just `git add` the file explicitly.

**Factual corrections folded in:**
- R1 — Baseline preset is **`default`**, not `basic` (the template has a `[tool.pyrefly]` section; `basic` only auto-applies to fully unconfigured projects). The change is `default → strict`. (§Context)
- R2 — Coverage command is **`pyrefly coverage report`**, not `pyrefly report`. (§4)
- Config keys confirmed hyphenated; `preset`/`strict` confirmed real; pyrefly 1.0.0 and ruff/ruff-pre-commit v0.15.14 confirmed current; non-semver policy confirmed.

**Design changes folded in:**
- R3 — Replaced inline shell-in-JSON with a wrapper script `template/.claude/hooks/lint-typecheck.sh` (robust exit-2 handling, testable). (§3a)
- R4 — Hook `timeout` raised 60 → 120s (cold uv resolve on first scaffold). (§3a)
- R5 — Guide moved from root `docs/guides/` to **`template/docs/guides/`** so scaffolded projects actually receive it (root never ships). (§4)
- R6 — `tests/` are in scope under `strict`; added an explicit keep-vs-exclude decision. (§5, Open questions)

**Still-open / advisory (not blocking; tracked in Open questions and below):**
- R7 — ruff version can diverge between the `pre-commit` pinned `rev` and the `pyproject.toml` `ruff>=` floor (the pre-commit hook uses its own ruff; the local pyrefly hook uses `uv run`). Add a convention note in the guide to bump both together. **TODO in §4/implementation.**
- R8 — `dependabot.yml` (`uv` ecosystem, weekly) will propose pyrefly bumps that may break CI given non-semver; the guide should warn against blind auto-merge of pyrefly PRs. **TODO in §4.**
- R9 — When authoring the skill, avoid an *unintended* literal uppercase `PACKAGE` token in `SKILL.md` (proj-init's `sed` substitution is case-sensitive and would rewrite it). Lowercase "package" is safe; `PACKAGE/cli.py`-style path placeholders are actually desirable to substitute. (§3c)
- R10 (**resolved**) — The template no longer commits a personal `settings.local.json`. The ~50 permission grants moved into the shared, committed `settings.json` (its natural home), `template/.claude/settings.local.json` was dropped, and both the root `.gitignore` override and the `template/.gitignore` negation that un-ignored it were removed — so personal `settings.local.json` files are now correctly ignored in both the template repo and scaffolded projects.
- R11 (pre-existing, out of scope) — The template repo does not dogfood its own shipped Stop hook (the hook lives under `template/.claude/`, not the repo-root `.claude/`); adding a root `.claude/settings.json` would make the template self-enforce, but that's separate from what scaffolded projects receive.

## Log

### Implementation (2026-05-25)

Implemented in the order specified, committing in logical chunks on `feature/upgrade-lint-typecheck`.

**Pre-implementation validation** (throwaway dirs in `/tmp`):
- Confirmed `pyrefly 1.0.0` and `ruff 0.15.14` resolve via `uv`.
- `pyrefly init` confirmed hyphenated config keys (`project-includes`).
- Validated the `strict` + `tests/**` sub-config (Option C): strict *alone* errors on an unannotated `tmp_path` fixture param (`[implicit-any-parameter]`); strict *with* the sub-config disabling `implicit-any` in `tests/**` → 0 errors. So the sub-config does real work, and the relaxation is scoped to `tests/`.
- Confirmed the real template stub signatures (`hello() -> None`, `test_placeholder()` with no return annotation) pass `strict` clean.

**Changes made:**
- §1 — `.pre-commit-config.yaml` ruff rev `v0.15.5 → v0.15.14`; `pyproject.toml` dev pins `pyrefly>=1.0.0`, `ruff>=0.15`.
- §2 — `[tool.pyrefly]` now sets `preset = "strict"`, adds `project-excludes`, and the `[[tool.pyrefly.sub-config]]` `tests/**` block disabling `implicit-any`. Annotated the shipped `test_placeholder() -> None` to model good practice.
- §3a — Added `template/.claude/settings.json` (shared `Stop` hook, `timeout: 120`) and the executable wrapper `template/.claude/hooks/lint-typecheck.sh` (runs `ruff check` + `pyrefly check`, exit 2 if either fails). Verified neither is gitignored.
- §3b — Added a "Before finishing a task" directive and a guide cross-link to `template/CLAUDE.md`. Decided against shipping `AGENTS.md` — the template is Claude-Code-specific (ships `.claude/`), so `CLAUDE.md` is the right home.
- §3c — Added `template/.claude/skills/lint-and-typecheck/SKILL.md`. Authored directly (the skill-creator eval loop is disproportionate for a deterministic, template-shipped workflow skill). No literal uppercase `PACKAGE` token in the body (R9); verified.
- §4 — Added `template/docs/guides/lint-and-typecheck.md` (combined ruff + pyrefly guide), including the R7 "keep ruff versions in step" note and the R8 "don't blind-auto-merge pyrefly dependabot PRs" warning.
- Also updated the root `README.md` "Template structure" block for the new `.claude/` files and guide.

**Verification (§6):** Replicated the scaffold locally (`rsync` + `PACKAGE` substitution) into `/tmp/scaffoldtest` — avoiding `proj-init.sh`'s side effects (license fetch, `stanza init`, `git push origin dev`). Results:
- `uv sync --all-groups` resolved `pyrefly==1.0.0`, `ruff==0.15.14`.
- `ruff check`, `ruff format --check`, `pyrefly check` (strict), and `pytest` all pass clean on the scaffold.
- `pre-commit run --all-files` passes with the bumped ruff rev (all three hooks Passed).
- Stop hook exercised: exit 0 on clean code; exit 2 with the pyrefly error on stderr when a `[bad-return]` type error was injected (confirming the agent-feedback path).
- Sub-config smoke test on the scaffold: unannotated `tmp_path` fixture param → 0 errors; a genuine type mismatch in `tests/` → still flagged.

**Deviations from plan:**
- The plan's §6 "update `CHANGELOG.md`" doesn't map to a real file — the root repo has no `CHANGELOG.md` (it tracks version via `VERSION`, currently `0.3.3a0`); `template/CHANGELOG.md` is the placeholder that ships to scaffolded projects and should not carry proj-template's own history. Updated the root `README.md` structure block instead.
- Did **not** run `stanza release` on the feature branch — alpha bumps belong on `dev` after merge. The version bump and PR merge are deferred to `/plan-close`.

## Retrospective

- **The upfront expert-fleet review paid off.** Nearly every implementation decision was pre-settled in the plan (Stop-hook schema, hyphenated config keys, Option C, guide placement), so implementation was mechanical. The few surprises were caught not by the plan but by *validating in `/tmp` before editing* — confirming the sub-config actually relaxes `implicit-any` (and that strict alone would have errored) turned an assumption into a tested fact.
- **Verify steps should be checked against real repo state when planning.** §6's "update `CHANGELOG.md`" assumed a file that doesn't exist here; the root repo versions via `VERSION`, and `template/CHANGELOG.md` is a scaffold placeholder. A quick `ls` during planning would have flagged it. Resolved by updating the README structure block instead.
- **Author deterministic workflow skills directly; reserve the skill-creator eval loop for skills with subjective or hard-to-predict output.** The full benchmark/eval-viewer loop would have been disproportionate for a fixed ruff+pyrefly workflow that ships in a template.
- **The wrapper-script approach for the Stop hook was the right call.** Keeping shell logic in `lint-typecheck.sh` (not inline JSON) made the exit-2 path independently testable, and the live test confirmed the docs' claim: exit 2 + stderr feeds errors back to the agent.
- **Verifying via a local `rsync` scaffold (not `proj-init.sh`) was the key testing insight** — it faithfully reproduces what scaffolded projects receive (including `PACKAGE` substitution and the new `.claude/` files) without `proj-init.sh`'s side effects (license fetch, `stanza init`, `git push origin dev`).
- **Follow-ups left open** (out of scope, tracked in §Open questions / Review findings): R7/R8 are now documented in the guide; R10 (template ships personal `settings.local.json`) and R11 (template doesn't dogfood its own Stop hook at repo root) remain candidates for a separate cleanup.

