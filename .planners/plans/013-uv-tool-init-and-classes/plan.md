---
id: 13
slug: uv-tool-init-and-classes
status: draft
branch:
created: 2026-11-09T16:05:37-08:00
concluded:
pr:
---

# Add init, more file classes, and the skill preflight to the repotemplates CLI

## Plan

### Goal

Finish the `repotemplates` CLI that plan 012 started. 012 shipped the package,
the per-release manifest, `check` for one repo and for a repos directory, and
`version`. This plan inherits what 012 left open: its step e (`init`), the skill
half of its step f, its open questions 1, 4, and 5, and the PyPI setup.

### Inherited from plan 012

Open questions, keeping 012's numbers so earlier notes still resolve:

1. (012 q1) Does `init` port `scripts/init.sh` to Python, or call the bash
   script it ships? The bash script supports a fresh machine with no uv (curl to
   bash), which the tool cannot replace.
4. (012 q4) Does upgrade become a command (`repotemplates upgrade`, applying the
   mechanical part of the sync matrix), or stay in the `install-template` skill,
   informed by `check`?
5. (012 q5) Which file classes beyond the Claude hooks are template-owned for
   `check`: pre-commit config, CI workflows, `.gitignore`? Each needs its own
   comparison rule, and where repos legitimately diverge an `absent by design`
   status (e.g. `renovate.yml` in a repo on Dependabot).

Remaining work, in order:

a. **PyPI setup** (waits on the owner): add the PyPI pending publisher (project
   `repotemplates`, workflow `publish.yml`, environment `pypi`), create the
   `pypi` environment, and set `PUBLISH_ENABLED`. Then cut the first release
   that publishes, and confirm it on PyPI.
b. **Skill preflight**: the `install-template` skill's upgrade preflight reads
   `repotemplates check --json` instead of hashing files by hand. Better after
   a, so the skill can install the tool by name (`uvx repotemplates`).
c. **More file classes** (question 5), each with fixture tests, starting with
   whichever class the fleet shows drifting most.
d. **`init`** (012's step e), once question 1 is answered. The curl-to-bash
   path in the README keeps working.

Not verified at 012's close, and checked here:

- `publish.yml` has never run on GitHub; step a is its first run.

### Out of scope

- Plan 011 (multiple templates). When it lands, it changes
  `paths.template_root()` and teaches `read_stamp` the stamp's `template` key;
  that work belongs to 011.
