"""The ruff-pre-commit rev and the repo's locked ruff, which are kept equal.

The commit hook installs its own ruff at the ``rev`` in
``.pre-commit-config.yaml``, while CI and the Stop hook run the ruff in
``uv.lock``. When the two differ, a commit can pass the hook and then fail
``ruff format --check`` in CI. So the rev always equals the locked ruff, and the
template's rev is a floor, not a value to copy:

- when the lock (and so the rev) is older than the template's rev, both move to
  it, as long as the repo's ``ruff`` range in ``pyproject.toml`` allows it;
- when the lock is newer, the rev follows the lock.

``check`` reports a rev that differs from the lock; ``upgrade`` moves the rev
and relocks ruff to the version it writes.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from repotemplates.classes import _REPO, _REV, pins, version_cmp

__all__ = [
    "PRECOMMIT",
    "RUFF_HOOK",
    "RuffReport",
    "in_range",
    "locked_ruff",
    "relock_command",
    "ruff_report",
    "ruff_specs",
    "set_rev",
]

PRECOMMIT = ".pre-commit-config.yaml"
RUFF_HOOK = "https://github.com/astral-sh/ruff-pre-commit"

_REQ = re.compile(
    r"^\s*ruff(?![\w.-])\s*(?:\[[^\]]*\])?\s*(?P<spec>[^;]*)", re.IGNORECASE
)
_CLAUSE = re.compile(r"^\s*(?P<op>~=|===|==|!=|<=|>=|<|>)\s*(?P<v>[^\s,]+)\s*$")


@dataclass(frozen=True)
class RuffReport:
    """The ruff-pre-commit rev against the locked ruff.

    ``status``: same (the rev equals the lock), differs, or unlocked (no ruff in
    ``uv.lock``, so there is nothing to keep the rev equal to).
    ``target`` is the version both should be at: the newer of the lock and the
    template's rev, or the lock when the repo's ruff range excludes the
    template's. None when it cannot be told. ``detail`` says why, when the
    target is not the template's.
    """

    rev: str
    locked: tuple[str, ...]
    template: str | None
    status: str
    target: str | None
    detail: str = ""

    @property
    def relock(self) -> bool:
        """Whether the lock has to move to reach the target."""
        return self.target is not None and self.locked != (self.target,)


def _plain(version: str) -> str:
    return version.removeprefix("v")


def rev_of(text: str) -> str | None:
    """The ruff-pre-commit rev in a pre-commit config, as written."""
    return next((p.version for p in pins(text) if p.name == RUFF_HOOK), None)


def locked_ruff(repo: Path) -> tuple[str, ...]:
    """Every ruff version ``uv.lock`` pins, lowest first; empty when none."""
    try:
        data = tomllib.loads((repo / "uv.lock").read_text())
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return ()
    found = {
        pkg["version"]
        for pkg in data.get("package", [])
        if isinstance(pkg, dict)
        and pkg.get("name") == "ruff"
        and isinstance(pkg.get("version"), str)
    }
    return tuple(sorted(found, key=_sort))


def _sort(version: str) -> tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", version))


def ruff_specs(repo: Path) -> list[str]:
    """The version specifiers every ``ruff`` requirement in ``pyproject.toml``
    sets: the dependencies, the optional ones, and the dependency groups."""
    try:
        data = tomllib.loads((repo / "pyproject.toml").read_text())
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return []
    project = data.get("project", {})
    lists: list[object] = [project.get("dependencies", [])]
    lists += list((project.get("optional-dependencies") or {}).values())
    lists += list((data.get("dependency-groups") or {}).values())
    specs: list[str] = []
    for items in lists:
        for item in items if isinstance(items, list) else []:
            if isinstance(item, str) and (m := _REQ.match(item)):
                if m["spec"].strip():
                    specs.append(m["spec"].strip())
    return specs


def _satisfies(version: str, op: str, bound: str) -> bool | None:
    if bound.endswith(".*") and op in ("==", "!="):
        prefix = bound[:-2].split(".")
        match = version.split(".")[: len(prefix)] == prefix
        return match if op == "==" else not match
    result = version_cmp(version, bound)
    if result is None:
        return None
    if op == "~=":
        parts = bound.split(".")
        if len(parts) < 2:
            return None
        upper = [*parts[:-2], str(int(parts[-2]) + 1)]
        below = version_cmp(version, ".".join(upper))
        return None if below is None else result >= 0 and below < 0
    return {
        "==": result == 0,
        "===": version == bound,
        "!=": result != 0,
        "<": result < 0,
        "<=": result <= 0,
        ">": result > 0,
        ">=": result >= 0,
    }[op]


def in_range(version: str, specs: list[str]) -> bool | None:
    """Whether ``version`` meets every specifier; None when one cannot be read."""
    for spec in specs:
        for clause in spec.split(","):
            if not clause.strip():
                continue
            m = _CLAUSE.match(clause)
            if m is None:
                return None
            ok = _satisfies(version, m["op"], m["v"])
            if ok is None:
                return None
            if not ok:
                return False
    return True


def ruff_report(
    repo: Path, template: Path, *, precommit: str | None = None
) -> RuffReport | None:
    """The rev against the lock, or None when the repo pins no ruff-pre-commit.

    ``precommit`` checks planned content before a local config is written.
    """
    if precommit is None:
        try:
            precommit = (repo / PRECOMMIT).read_text()
        except (OSError, UnicodeDecodeError):
            return None
    rev = rev_of(precommit)
    if rev is None:
        return None
    try:
        theirs = rev_of((template / PRECOMMIT).read_text())
    except (OSError, UnicodeDecodeError):
        theirs = None
    floor = _plain(theirs) if theirs else None
    locked = locked_ruff(repo)
    if not locked:
        return RuffReport(rev, locked, theirs, "unlocked", None)
    status = "same" if locked == (_plain(rev),) else "differs"
    if len(locked) > 1:
        detail = f"uv.lock pins several ruff versions ({', '.join(locked)})"
        return RuffReport(rev, locked, theirs, status, None, detail)
    lock = locked[0]
    if floor is None or (version_cmp(lock, floor) or 0) >= 0:
        return RuffReport(rev, locked, theirs, status, lock)
    specs = ruff_specs(repo)
    allowed = in_range(floor, specs)
    if allowed is False:
        detail = (
            f"the template's {theirs} is outside the repo's ruff range "
            f"({'; '.join(specs)}): widen it in pyproject.toml, then upgrade again"
        )
        return RuffReport(rev, locked, theirs, status, lock, detail)
    if allowed is None:
        detail = f"the repo's ruff range ({'; '.join(specs)}) could not be read"
        return RuffReport(rev, locked, theirs, status, None, detail)
    return RuffReport(rev, locked, theirs, status, floor)


def set_rev(text: str, version: str) -> str:
    """The pre-commit config with the ruff-pre-commit rev set to ``v<version>``,
    keeping its quotes and any trailing comment."""
    lines = text.split("\n")
    repo: str | None = None
    for i, line in enumerate(lines):
        if m := _REPO.match(line):
            repo = m["name"]
        if repo == RUFF_HOOK and (m := _REV.match(line)):
            ref = f"v{_plain(version)}"
            lines[i] = f"{m['head']}{m['q']}{ref}{m['q']}{m['tail'] or ''}"
            break
    return "\n".join(lines)


def relock_command(version: str) -> str:
    """The uv command that moves the locked ruff to exactly ``version``. A bare
    ``--upgrade-package ruff`` takes the newest release instead."""
    return f"uv lock --upgrade-package ruff=={_plain(version)}"
