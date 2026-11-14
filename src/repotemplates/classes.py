"""Comparison rules for the template-owned files beyond the Claude hooks.

Each class has its own idea of "the same file":

- **Pinned** files (the pre-commit config and the workflows) compare with their
  pins masked: ``rev:`` values, action refs and their version comments, and a
  ``python-version`` matrix list, which follows each repo's ``requires-python``.
  The pins are compared on their own, by name, and a repo whose pin is newer
  than the template's is ahead, not drifted: Dependabot moves consumers first.
- **Config** files (Dependabot, Renovate) compare by exact content.
- **Ignore** files (``.gitignore``, ``.gitattributes``) compare by behaviour,
  with local additions allowed: each template rule must hold in the repo, which
  git itself answers for a probe path built from the rule. The fleet spells one
  rule several ways (``.claude``, ``.claude/``, ``.claude/*``), so line text is
  the wrong test.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "CONFIG",
    "GITATTRIBUTES",
    "GITIGNORE",
    "IGNORE",
    "PINNED",
    "Pin",
    "attribute_gaps",
    "compare_pins",
    "ignore_gaps",
    "mask",
    "merge_pinned",
    "pins",
    "version_cmp",
]

PINNED = (
    ".pre-commit-config.yaml",
    ".github/workflows/test.yml",
    ".github/workflows/publish.yml",
    ".github/workflows/renovate.yml",
)
CONFIG = (".github/dependabot.yml", ".github/renovate.json")
GITIGNORE = ".gitignore"
GITATTRIBUTES = ".gitattributes"
IGNORE = (GITIGNORE, GITATTRIBUTES)

_REPO = re.compile(r"^\s*-?\s*repo:\s*['\"]?(?P<name>[^'\"\s#]+)")
_REV = re.compile(
    r"^(?P<head>\s*rev:\s*)(?P<q>['\"]?)(?P<ref>[^'\"\s#]+)(?P=q)(?P<tail>\s*#.*)?$"
)
_USES = re.compile(
    r"^(?P<head>\s*(?:-\s*)?uses:\s*)(?P<q>['\"]?)(?P<name>[^@'\"\s]+)@"
    r"(?P<ref>[^'\"\s#]+)(?P=q)(?P<tail>\s*#\s*(?P<comment>\S+).*)?$"
)
_MATRIX = re.compile(r"^(?P<head>\s*python-version:\s*)\[.*\]\s*$")
_VERSION = re.compile(r"^v?(\d+(?:\.\d+)*)$")


@dataclass(frozen=True)
class Pin:
    """One pinned dependency: a hook repo or an action, and the release it names.

    ``version`` is the action's version comment when it has one (the ref is then
    a commit SHA), else the ref itself.
    """

    name: str
    version: str
    line: int


def mask(text: str) -> str:
    """The file with every pin and the Python matrix list replaced by a marker."""
    out: list[str] = []
    for line in text.split("\n"):
        if m := _REV.match(line):
            line = f"{m['head']}<pin>"
        elif m := _USES.match(line):
            line = f"{m['head']}{m['name']}@<pin>"
        elif m := _MATRIX.match(line):
            line = f"{m['head']}<matrix>"
        out.append(line)
    return "\n".join(out)


def pins(text: str) -> list[Pin]:
    found: list[Pin] = []
    repo: str | None = None
    for number, line in enumerate(text.split("\n")):
        if m := _REPO.match(line):
            repo = m["name"]
        if (m := _REV.match(line)) and repo is not None:
            found.append(Pin(repo, m["ref"], number))
        elif m := _USES.match(line):
            # A SHA ref names its release in the comment; any other comment
            # ("# keep") says nothing about the version
            comment = m["comment"]
            version = comment if comment and _key(comment) else m["ref"]
            found.append(Pin(m["name"], version, number))
    return found


def _key(version: str) -> tuple[int, ...] | None:
    m = _VERSION.match(version)
    return tuple(int(p) for p in m.group(1).split(".")) if m else None


def _cmp(ours: str, theirs: str) -> int | None:
    """-1, 0, or 1 for ours against theirs; None when either is not a version."""
    if ours == theirs:
        return 0
    a, b = _key(ours), _key(theirs)
    if a is None or b is None:
        return None
    width = max(len(a), len(b))
    a, b = a + (0,) * (width - len(a)), b + (0,) * (width - len(b))
    return (a > b) - (a < b)


def version_cmp(ours: str, theirs: str) -> int | None:
    """-1, 0, or 1 for one version against another, a leading ``v`` allowed on
    either; None when either is not a plain dotted version."""
    return _cmp(ours.removeprefix("v"), theirs.removeprefix("v"))


def compare_pins(repo_text: str, template_text: str) -> str:
    """same, ahead, behind, mixed, or differs: the repo's pins against the template's.

    Only names both files pin are compared. ``differs`` is a pin that is not a
    version on one side (a bare SHA) and is not equal.
    """
    template = {p.name: p.version for p in pins(template_text)}
    seen: set[int] = set()
    for pin in pins(repo_text):
        if pin.name not in template:
            continue
        result = _cmp(pin.version, template[pin.name])
        if result is None:
            return "differs"
        seen.add(result)
    if seen <= {0}:
        return "same"
    if seen <= {0, 1}:
        return "ahead"
    if seen <= {0, -1}:
        return "behind"
    return "mixed"


def merge_pinned(template_text: str, repo_text: str) -> str:
    """The template's file, keeping what the repo legitimately holds of its own.

    A pin the repo has newer than the template's stays, and so does the repo's
    Python matrix list when both files have exactly one. Everything else is the
    template's.
    """
    repo_pins: dict[str, tuple[str, str]] = {}
    repo_lines = repo_text.split("\n")
    for pin in pins(repo_text):
        repo_pins.setdefault(pin.name, (pin.version, repo_lines[pin.line]))
    repo_matrix = [line for line in repo_lines if _MATRIX.match(line)]
    template_lines = template_text.split("\n")
    template_matrix = [line for line in template_lines if _MATRIX.match(line)]
    by_line = {p.line: p for p in pins(template_text)}
    out: list[str] = []
    for number, line in enumerate(template_lines):
        pin = by_line.get(number)
        if pin is not None and pin.name in repo_pins:
            version, repo_line = repo_pins[pin.name]
            if _cmp(version, pin.version) == 1:
                line = _same_indent(line, repo_line)
        elif _MATRIX.match(line) and len(repo_matrix) == len(template_matrix) == 1:
            line = _same_indent(line, repo_matrix[0])
        out.append(line)
    return "\n".join(out)


def _same_indent(template_line: str, repo_line: str) -> str:
    """The repo's line, re-indented to sit where the template's does."""
    indent = template_line[: len(template_line) - len(template_line.lstrip())]
    return indent + repo_line.lstrip()


# --- ignore files -----------------------------------------------------------

_PROBE = "rtprobe"


def _rules(text: str) -> list[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _probe(pattern: str) -> str:
    """A path the pattern matches: globs filled in, a directory given a child."""
    path = pattern.lstrip("/").replace("**", "a").replace("*", _PROBE)
    path = path.replace("?", "x")
    return f"{path}{_PROBE}" if path.endswith("/") else path


def _git(
    repo: Path, *args: str, stdin: str | None = None
) -> subprocess.CompletedProcess[str]:
    # The user's own excludes and attributes files would answer for the repo
    config = [
        "-c",
        "core.excludesFile=/dev/null",
        "-c",
        "core.attributesFile=/dev/null",
    ]
    return subprocess.run(
        ["git", *config, *args], cwd=repo, input=stdin, capture_output=True, text=True
    )


def ignore_gaps(repo: Path, template_text: str) -> tuple[list[str], list[str]]:
    """The template's ignore rules that do not hold in the repo, and those waived.

    A rule holds when git ignores its probe path (or, for a ``!`` rule, does not).
    ``--no-index`` asks about the rules alone, so a tracked file does not answer.
    A rule that does not hold is waived when the repo tracks a path it would
    ignore: tracking ``.claude/settings.json`` is a choice not to ignore
    ``.claude/``, which is a per-repo decision, not drift.
    """
    rules = _rules(template_text)
    probes = [_probe(r.removeprefix("!")) for r in rules]
    ignored = _ignored(repo, probes)
    gaps: list[str] = []
    waived: list[str] = []
    for i, (rule, probe) in enumerate(zip(rules, probes, strict=True)):
        if (probe in ignored) != rule.startswith("!"):
            continue
        (waived if _tracks(repo, rules, i) else gaps).append(rule)
    return gaps, waived


def _tracks(repo: Path, rules: Sequence[str], i: int) -> bool:
    """Whether the repo tracks a path the template's rule ``rules[i]`` ignores.

    git matches the rule as a gitignore pattern, together with the template's
    later negations: ``.env.*`` does not claim a tracked ``.env.example`` while
    the template's own ``!.env.example`` un-ignores it.
    """
    if rules[i].startswith("!"):
        return False
    later = [r for r in rules[i + 1 :] if r.startswith("!")]
    excludes = [f"--exclude={r}" for r in (rules[i], *later)]
    result = _git(repo, "ls-files", "--cached", "--ignored", *excludes)
    return result.returncode == 0 and bool(result.stdout.strip())


def _ignored(repo: Path, probes: Sequence[str]) -> set[str]:
    stdin = "\n".join(probes) + "\n"
    result = _git(repo, "check-ignore", "--no-index", "--stdin", stdin=stdin)
    # 1 is "nothing ignored", not a failure
    if result.returncode not in (0, 1):
        raise OSError(result.stderr.strip() or "git check-ignore failed")
    return set(result.stdout.splitlines())


def _expected(attr: str) -> tuple[str, str]:
    """An attribute spec as git check-attr reports it: (name, value)."""
    if attr.startswith("-"):
        return attr[1:], "unset"
    if attr.startswith("!"):
        return attr[1:], "unspecified"
    name, sep, value = attr.partition("=")
    return name, value if sep else "set"


def attribute_gaps(repo: Path, template_text: str) -> list[str]:
    """The template's attribute lines that do not hold in the repo."""
    gaps: list[str] = []
    for line in _rules(template_text):
        pattern, *attrs = line.split()
        probe = _probe(pattern)
        for name, value in (_expected(a) for a in attrs):
            result = _git(repo, "check-attr", name, "--", probe)
            if result.returncode != 0:
                raise OSError(result.stderr.strip() or "git check-attr failed")
            got = result.stdout.strip().rsplit(": ", 1)[-1]
            if got != value:
                gaps.append(line)
                break
    return gaps
