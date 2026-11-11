"""The mechanical part of a template upgrade.

``upgrade`` rewrites a template-owned file only when ``check`` shows nothing of
the repo's own in it would be lost:

- a file that equals an earlier release (``matches``) takes the template's copy.
  A pinned file keeps the repo's newer pins and its Python matrix
  (``classes.merge_pinned``), and the settings file has only its ``hooks`` block
  replaced;
- a pinned file that is current but for pins behind the template has those pins
  raised, and keeps the ones that are ahead.

Everything else is reported and left alone, for the ``install-template`` skill:
a one-off (customized) file, a missing one (copy it, or declare it in ``omit``),
an ignore file lacking rules, a retired one, a pin that is not a version. The
stamp moves to this release last, and only when every file then reads current or
omitted, so a stamp never overstates what the repo carries.
"""

from __future__ import annotations

import json
import re
import subprocess
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path

from repotemplates.check import (
    RAISABLE_PINS,
    STAMP_TABLES,
    FileReport,
    RepoReport,
    check_repo,
)
from repotemplates.classes import merge_pinned
from repotemplates.manifest import SETTINGS, SETTINGS_HOOKS, Manifest, file_path
from repotemplates.versions import sort_key

__all__ = ["Action", "UpgradePlan", "apply", "dirty", "plan_upgrade", "set_stamp"]

STAMP_COMMENT = (
    "# repotemplates release stamp, set by init.sh and install-template; "
    "inert to consumers."
)

# The first line of the comment above the stamp table, in any wording the
# template has shipped: the one-line form, and the four-line form from before
# 0.11.6. Comment lines of the repo's own above it are left alone.
_TEMPLATE_COMMENT = re.compile(
    r"^\s*#\s*(Which proj-template release|(proj-template|repotemplates) release stamp)"
)


@dataclass(frozen=True)
class Action:
    """``action``: write (upgrade rewrites it), keep (already current), or skip."""

    path: str
    action: str
    reason: str


@dataclass
class UpgradePlan:
    repo: str
    release: str
    actions: list[Action] = field(default_factory=list)
    # The stamp upgrade writes, or None when it leaves the stamp alone
    stamp: str | None = None
    stamp_reason: str = ""
    refused: str | None = None
    contents: dict[str, str] = field(default_factory=dict, repr=False)

    @property
    def complete(self) -> bool:
        """Whether the repo reads current once the plan is applied."""
        return self.refused is None and all(a.action != "skip" for a in self.actions)

    def to_dict(self) -> dict[str, object]:
        out = asdict(self)
        del out["contents"]
        out["complete"] = self.complete
        return out


def _skip_reason(f: FileReport) -> str:
    if f.status == "one-off":
        return "customized: matches no release; merge by hand"
    if f.status == "missing":
        return "missing: copy it in, or list it in the stamp's omit"
    if f.status == "partial":
        return f"lacks {', '.join(f.detail)}; add them, or track what they ignore"
    if f.status == "retired":
        return f"retired after v{f.release}; remove it if nothing uses it"
    if f.pins == "differs":
        return "a pin is not a version (a bare ref); compare it by hand"
    return f.status


def _settings_with_hooks(repo_raw: str, template_raw: str) -> str:
    data = json.loads(repo_raw)
    data["hooks"] = json.loads(template_raw)["hooks"]
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def _new_content(repo: Path, template: Path, f: FileReport) -> str | None:
    """What upgrade writes for this file, or None to leave it alone."""
    replaceable = (f.status == "matches" and f.pins != "differs") or (
        f.status == "current" and f.pins in RAISABLE_PINS
    )
    if not replaceable:
        return None
    if f.path == SETTINGS_HOOKS:
        return _settings_with_hooks(
            (repo / SETTINGS).read_text(), (template / SETTINGS).read_text()
        )
    theirs = (template / f.path).read_text()
    if f.kind == "pinned":
        return merge_pinned(theirs, (repo / f.path).read_text())
    return theirs


def plan_upgrade(
    repo: Path, template: Path, manifest: Manifest, installed: str
) -> UpgradePlan:
    report: RepoReport = check_repo(repo, template, manifest, installed)
    plan = UpgradePlan(repo=report.path, release=installed)
    # Compared with this release itself, not with the newest stable one the
    # stamp's status is read against: a prerelease stamp reads "alpha" whichever
    # side of the installed release it falls
    stamped = sort_key(report.stamp.version) if report.stamp.version else None
    release_key = sort_key(installed)
    if stamped and release_key and stamped > release_key:
        plan.refused = (
            f"the repo is stamped {report.stamp.version}, newer than this release "
            f"({installed}); run a newer repotemplates"
        )
        return plan
    root = Path(report.path)
    for f in report.files:
        if f.current:
            plan.actions.append(Action(f.path, "keep", f.status))
            continue
        content = _new_content(root, template, f)
        if content is None:
            plan.actions.append(Action(f.path, "skip", _skip_reason(f)))
            continue
        plan.contents[file_path(f.path)] = content
        reason = f"matches v{f.release}" if f.status == "matches" else f"pins {f.pins}"
        plan.actions.append(Action(f.path, "write", reason))
    skipped = sum(a.action == "skip" for a in plan.actions)
    if skipped:
        plan.stamp_reason = (
            f"left at {report.stamp.version or 'none'}: {skipped} file(s) still "
            "differ, and a stamp that overstates makes the next upgrade skip the repo"
        )
    elif not (root / "pyproject.toml").is_file():
        plan.actions.append(Action("pyproject.toml", "skip", "missing: no stamp"))
        plan.stamp_reason = "no pyproject.toml to stamp"
    else:
        try:
            text = (root / "pyproject.toml").read_text()
            stamped = set_stamp(text, installed)
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            # tomllib's TOMLDecodeError is a ValueError
            reason = f"cannot set the stamp: {exc}"
            plan.actions.append(Action("pyproject.toml", "skip", reason))
            plan.stamp_reason = f"left at {report.stamp.version or 'none'}: {reason}"
            return plan
        if stamped == text:
            plan.stamp_reason = f"already {installed}"
            return plan
        plan.contents["pyproject.toml"] = stamped
        plan.stamp = installed
        if report.stamp.version != installed:
            plan.stamp_reason = f"{report.stamp.version or 'none'} -> {installed}"
        elif report.stamp.table != "tool.repotemplates":
            plan.stamp_reason = f"already {installed}; table renamed"
        else:
            plan.stamp_reason = f"already {installed}; stamp comment refreshed"
    return plan


# A table or an array-of-tables header
_HEADER = re.compile(r"^\s*(?P<head>\[\[?[^\[\]]+\]\]?)\s*(#.*)?$")
_VERSION_KEY = re.compile(r"""^\s*(version|"version"|'version')\s*=""")

Key = tuple[str, ...]
_NEW: Key = ("tool", "repotemplates")
_OLD: Key = ("tool", "proj-template")
_SCRIPTS: Key = ("project", "scripts")


def _in_strings(lines: list[str]) -> set[int]:
    """The lines that start inside a multi-line string, where what looks like a
    header or a key is text. Assumes the lines parse as TOML."""
    inside: set[int] = set()
    quote: str = ""
    for n, line in enumerate(lines):
        if quote:
            inside.add(n)
        i = 0
        while i < len(line):
            if quote:
                if quote == '"""' and line[i] == "\\":
                    i += 2
                elif line.startswith(quote, i):
                    i += 3
                    # Up to two more quotes close it: they end the string's text
                    while i < len(line) and line[i] == quote[0]:
                        i += 1
                    quote = ""
                else:
                    i += 1
            elif line[i] == "#":
                break
            elif line.startswith(('"""', "'''"), i):
                quote = line[i : i + 3]
                i += 3
            elif line[i] in "\"'":
                close = line[i]
                i += 1
                while i < len(line) and line[i] != close:
                    i += 2 if close == '"' and line[i] == "\\" else 1
                i += 1
            else:
                i += 1
    return inside


def _table_key(head: str) -> Key:
    """The key a header names, read as TOML reads it, so ``[tool."repotemplates"]``
    is the stamp table. An array of tables keeps a marker, so
    ``[[tool.repotemplates]]`` never is."""
    if head.startswith("[["):
        return ("[[", head)
    try:
        node: object = tomllib.loads(head)
    except tomllib.TOMLDecodeError:
        return ("?", head)
    key: list[str] = []
    while isinstance(node, dict) and len(node) == 1:
        name, node = next(iter(node.items()))
        key.append(str(name))
    return tuple(key)


def _tables(lines: list[str], inside: set[int]) -> list[tuple[int, Key]]:
    return [
        (i, _table_key(m["head"]))
        for i, line in enumerate(lines)
        if i not in inside and (m := _HEADER.match(line))
    ]


def _comment_start(lines: list[str], at: int, inside: set[int]) -> int | None:
    """Where the template's comment above the header at ``at`` starts, if the
    comment block there holds one."""
    top = at
    while top > 0 and top - 1 not in inside and lines[top - 1].lstrip().startswith("#"):
        top -= 1
    return next((i for i in range(top, at) if _TEMPLATE_COMMENT.match(lines[i])), None)


def _drop_table(
    lines: list[str], tables: list[tuple[int, Key]], index: int, inside: set[int]
) -> list[str]:
    """``lines`` without the table ``tables[index]`` names, or its template
    comment."""
    at = tables[index][0]
    start = _comment_start(lines, at, inside)
    head = lines[: at if start is None else start]
    if index + 1 < len(tables):
        return head + lines[tables[index + 1][0] :]
    while head and head[-1] == "":
        head.pop()
    return head + [""] if lines[-1] == "" else head


def _stamps(text: str) -> dict[str, dict[str, object]]:
    """The stamp tables ``text`` holds, by name. Raises ValueError when it does
    not parse, or a stamp is not a table or has an ``omit`` that is not a list
    of paths, which a restamp would carry into a stamp ``check`` cannot read."""
    tool = tomllib.loads(text).get("tool", {})
    if not isinstance(tool, dict):
        raise ValueError("tool is not a table")
    found: dict[str, dict[str, object]] = {}
    for name in STAMP_TABLES:
        if name not in tool:
            continue
        section = tool[name]
        if not isinstance(section, dict):
            raise ValueError(f"tool.{name} is not a table")
        omit = section.get("omit", [])
        if not isinstance(omit, list) or not all(isinstance(o, str) for o in omit):
            raise ValueError(f"tool.{name} omit is not a list of paths")
        found[name] = section
    return found


def _value(line: str) -> object:
    """The value a ``version = ...`` line sets, or None when it does not parse."""
    try:
        return tomllib.loads(line).get("version")
    except tomllib.TOMLDecodeError:
        return None


def set_stamp(text: str, release: str) -> str:
    """``pyproject.toml`` with ``[tool.repotemplates] version`` set to ``release``.

    Renames an old ``[tool.proj-template]`` table, or drops it when the repo has
    both, and adds the table after ``[project.scripts]`` (or at the end) when the
    repo has neither. Keeps CRLF line endings. Raises ValueError for a file it
    cannot stamp safely (see ``_stamps``), and for a stamp written as an inline
    table or dotted keys, which it leaves alone only when it holds ``release``.
    """
    crlf = "\r\n" in text and text.count("\r\n") == text.count("\n")
    body = text.replace("\r\n", "\n") if crlf else text
    stamps = _stamps(body)
    lines = body.split("\n")
    inside = _in_strings(lines)
    tables = _tables(lines, inside)
    keys = [key for _, key in tables]
    for name, section in stamps.items():
        if ("tool", name) in keys:
            continue
        if list(stamps) == ["repotemplates"] and section.get("version") == release:
            return text
        raise ValueError(f"tool.{name} is not a [tool.{name}] table; stamp it by hand")
    if _NEW in keys and _OLD in keys:
        lines = _drop_table(lines, tables, keys.index(_OLD), inside)
        inside = _in_strings(lines)
        tables = _tables(lines, inside)
        keys = [key for _, key in tables]
    version_line = f'version = "{release}"'
    for old in (_NEW, _OLD):
        if old not in keys:
            continue
        at = tables[keys.index(old)][0]
        end = next((i for i, _ in tables if i > at), len(lines))
        if old != _NEW:
            lines[at] = "[tool.repotemplates]"
        start = _comment_start(lines, at, inside)
        if start is not None and lines[start:at] != [STAMP_COMMENT]:
            lines[start:at] = [STAMP_COMMENT]
            end -= at - start - 1
            at = start + 1
            inside = _in_strings(lines)
        for i in range(at + 1, end):
            if i not in inside and _VERSION_KEY.match(lines[i]):
                if _value(lines[i]) != release:
                    lines[i] = version_line
                break
        else:
            lines.insert(at + 1, version_line)
        break
    else:
        block = [STAMP_COMMENT, "[tool.repotemplates]", version_line, ""]
        if _SCRIPTS in keys:
            at = tables[keys.index(_SCRIPTS)][0]
            end = next((i for i, _ in tables if i > at), None)
        else:
            end = None
        if end is None:
            if lines and lines[-1] == "":
                lines.pop()
            lines += ["", *block]
        else:
            lines[end:end] = block
    out = "\n".join(lines)
    stamps = _stamps(out)
    if (
        list(stamps) != ["repotemplates"]
        or stamps["repotemplates"].get("version") != release
    ):
        raise ValueError("could not set the stamp in pyproject.toml")
    return out.replace("\n", "\r\n") if crlf else out


def dirty(repo: Path, paths: list[str]) -> list[str]:
    """Tracked paths among ``paths`` with uncommitted changes."""
    if not paths:
        return []
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no", "--", *paths],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [line[3:] for line in result.stdout.splitlines()]


def apply(plan: UpgradePlan) -> None:
    """Write the plan. Every file, the stamped ``pyproject.toml`` included, was
    computed by ``plan_upgrade``, so a failure there writes nothing."""
    root = Path(plan.repo)
    for path, content in plan.contents.items():
        (root / path).write_text(content)
