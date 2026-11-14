"""The mechanical part of a template upgrade.

``upgrade`` rewrites a template-owned file only when ``check`` shows nothing of
the repo's own in it would be lost:

- a file that equals an earlier release (``matches``) takes the template's copy.
  A pinned file keeps the repo's newer pins and its Python matrix
  (``classes.merge_pinned``), and the settings file has only its ``hooks`` block
  replaced;
- a pinned file that is current but for pins behind the template has those pins
  raised, and keeps the ones that are ahead;
- an ignored file absent from both checkouts (``local``) takes the template's
  copy in the checkout where upgrade runs;
- the ruff-pre-commit rev moves to the locked ruff, or to the template's rev
  when the lock is older, and ruff is relocked to exactly that version
  (``repotemplates.ruff`` has the rule).

Everything else is reported and left alone, for the ``install-template`` skill:
a one-off (customized) file (merge it, or record it in ``keep``), a kept file
whose template copy has changed since it was reviewed, a missing one (copy it,
or declare it in ``omit``), an ignore file lacking rules, a retired one, a pin
that is not a version, and a file a linked worktree reads from the main
checkout because it ignores it. A file ``keep`` records is otherwise left as
it is and counts as current.

The stamp moves to this release last, and only when every file then reads
current or omitted, so a stamp never overstates what the repo carries.
"""

from __future__ import annotations

import json
import re
import shutil
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
    stamp_error,
)
from repotemplates.classes import merge_pinned
from repotemplates.manifest import SETTINGS, SETTINGS_HOOKS, Manifest, file_path
from repotemplates.ruff import PRECOMMIT, relock_command, ruff_report, set_rev
from repotemplates.versions import sort_key

__all__ = [
    "Action",
    "UpgradePlan",
    "apply",
    "dirty",
    "plan_stamp",
    "plan_upgrade",
    "set_stamp",
]

STAMP_COMMENT = (
    "# repotemplates release stamp, set by init.sh and install-template; "
    "inert to consumers."
)

# The first line of the comment above the stamp table, in each wording a
# release has shipped: the current line, and an older one-line and four-line
# form. Comment lines of the repo's own above it are left alone.
_TEMPLATE_COMMENT = re.compile(
    r"^\s*#\s*(Which proj-template release|(proj-template|repotemplates) release stamp)"
)


@dataclass(frozen=True)
class Action:
    """``action``: write (upgrade rewrites it), keep (already current), relock
    (``uv.lock`` takes the ruff the rev names), or skip."""

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
    # The ruff version apply relocks to, or None
    relock: str | None = None
    contents: dict[str, str] = field(default_factory=dict, repr=False)
    template: Path | None = field(default=None, repr=False)

    @property
    def complete(self) -> bool:
        """Whether the repo reads current once the plan is applied, but for a
        stamp held back with ``stamp=False``."""
        return self.refused is None and all(a.action != "skip" for a in self.actions)

    def to_dict(self) -> dict[str, object]:
        out = asdict(self)
        del out["contents"]
        del out["template"]
        out["complete"] = self.complete
        return out


def _skip_reason(f: FileReport) -> str:
    reason = _status_reason(f)
    if f.source is not None:
        # The worktree ignores the file, so a write here would not reach the branch
        reason += f"; read from the main checkout, {f.source}: fix it there"
    return reason


def _status_reason(f: FileReport) -> str:
    if f.status == "one-off":
        return (
            "customized: matches no release; merge by hand, or record it in the "
            "stamp's keep"
        )
    if f.status == "kept-behind":
        return (
            f"kept as reviewed against v{f.release}, and {f.detail[0]}: review "
            "the change, then move its keep release to this one"
        )
    if f.status == "missing":
        return "missing: copy it in, or list it in the stamp's omit"
    if f.status == "partial":
        return f"lacks {', '.join(f.detail)}; add them, or track what they ignore"
    if f.status == "retired":
        return f"retired after v{f.release}; remove it if nothing uses it"
    if f.pins == "differs":
        return "a pin is not a version (a bare ref); compare it by hand"
    if f.pins in RAISABLE_PINS:
        # A kept file, or one read from the main checkout, which upgrade does
        # not write
        return f"{f.status}, with pins {f.pins}; raise them by hand"
    return f.status


def _settings_with_hooks(repo_raw: str, template_raw: str) -> str:
    data = json.loads(repo_raw)
    data["hooks"] = json.loads(template_raw)["hooks"]
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def _new_content(repo: Path, template: Path, f: FileReport) -> str | None:
    """What upgrade writes for this file, or None to leave it alone."""
    if f.status == "local":
        return (template / file_path(f.path)).read_text()
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
    repo: Path,
    template: Path,
    manifest: Manifest,
    installed: str,
    *,
    stamp: bool = True,
) -> UpgradePlan:
    """What upgrade writes and skips. With ``stamp`` false the stamp is left for
    the ``install-template`` skill, which writes it once the rows ``check`` does
    not cover (``pyproject.toml`` tables, ``.python-version``) are settled too."""
    report: RepoReport = check_repo(repo, template, manifest, installed)
    plan = UpgradePlan(repo=report.path, release=installed, template=template.resolve())
    if (refusal := _newer_stamp(report, installed)) is not None:
        plan.refused = refusal
        return plan
    root = Path(report.path)
    for f in report.files:
        if f.current:
            reason = f"kept as of v{f.release}" if f.status == "kept" else f.status
            plan.actions.append(Action(f.path, "keep", reason))
            continue
        content = None if f.source else _new_content(root, template, f)
        if content is None:
            plan.actions.append(Action(f.path, "skip", _skip_reason(f)))
            continue
        plan.contents[file_path(f.path)] = content
        if f.status == "local":
            reason = "local: ignored; write the template's copy in this checkout"
        else:
            reason = (
                f"matches v{f.release}" if f.status == "matches" else f"pins {f.pins}"
            )
        plan.actions.append(Action(f.path, "write", reason))
    _plan_ruff(plan, report, root, template)
    skipped = sum(a.action == "skip" for a in plan.actions)
    if skipped:
        plan.stamp_reason = (
            f"left at {report.stamp.version or 'none'}: {skipped} file(s) still "
            "differ, and a stamp that overstates makes the next upgrade skip the repo"
        )
    elif not (root / "pyproject.toml").is_file():
        plan.actions.append(Action("pyproject.toml", "skip", "missing: no stamp"))
        plan.stamp_reason = "no pyproject.toml to stamp"
    elif not stamp:
        plan.stamp_reason = (
            f"left at {report.stamp.version or 'none'}: --no-stamp, so it is "
            "written once the rest of the upgrade lands"
        )
    elif (error := _plan_stamp_write(plan, report, installed)) is not None:
        plan.actions.append(Action("pyproject.toml", "skip", error))
        plan.stamp_reason = f"left at {report.stamp.version or 'none'}: {error}"
    return plan


def _newer_stamp(report: RepoReport, installed: str) -> str | None:
    """The refusal for a repo stamped newer than this release, or None.

    Compared with this release itself, not with the newest stable one the
    stamp's status is read against: a prerelease stamp reads "alpha" whichever
    side of the installed release it falls.
    """
    stamp_key = sort_key(report.stamp.version) if report.stamp.version else None
    release_key = sort_key(installed)
    if stamp_key and release_key and stamp_key > release_key:
        return (
            f"the repo is stamped {report.stamp.version}, newer than this release "
            f"({installed}); run a newer repotemplates"
        )
    return None


def _plan_stamp_write(
    plan: UpgradePlan, report: RepoReport, installed: str
) -> str | None:
    """Plan the stamped ``pyproject.toml``, when the stamp there has to change.
    The reason the stamp cannot be set, or None."""
    try:
        text = (Path(report.path) / "pyproject.toml").read_text()
        stamped = set_stamp(text, installed)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        # tomllib's TOMLDecodeError is a ValueError
        return f"cannot set the stamp: {exc}"
    if stamped == text:
        plan.stamp_reason = f"already {installed}"
        return None
    plan.contents["pyproject.toml"] = stamped
    plan.stamp = installed
    if report.stamp.version != installed:
        plan.stamp_reason = f"{report.stamp.version or 'none'} -> {installed}"
    elif report.stamp.table != "tool.repotemplates":
        plan.stamp_reason = f"already {installed}; table renamed"
    else:
        plan.stamp_reason = f"already {installed}; stamp comment refreshed"
    return None


def _plan_ruff(
    plan: UpgradePlan, report: RepoReport, root: Path, template: Path
) -> None:
    """Move the ruff-pre-commit rev to the target and plan the relock. A
    pre-commit config upgrade leaves alone (a one-off) is left for the skill."""
    ruff = report.ruff
    if ruff is None and PRECOMMIT in plan.contents:
        ruff = ruff_report(root, template, precommit=plan.contents[PRECOMMIT])
    if ruff is None:
        return
    if ruff.detail:
        plan.actions.append(Action("uv.lock (ruff)", "skip", ruff.detail))
    if ruff.target is None:
        return
    at = next((i for i, a in enumerate(plan.actions) if a.path == PRECOMMIT), None)
    if at is None or plan.actions[at].action == "skip":
        return
    text = plan.contents.get(PRECOMMIT)
    if text is None:
        text = (root / PRECOMMIT).read_text()
    moved = set_rev(text, ruff.target)
    if moved != text:
        plan.contents[PRECOMMIT] = moved
        old = plan.actions[at]
        note = f"ruff rev v{ruff.target}, the locked ruff"
        reason = note if old.action == "keep" else f"{old.reason}; {note}"
        plan.actions[at] = Action(PRECOMMIT, "write", reason)
    if ruff.relock:
        plan.relock = ruff.target
        was = ", ".join(ruff.locked)
        reason = f"ruff {was} -> {ruff.target}: `{relock_command(ruff.target)}`"
        plan.actions.append(Action("uv.lock", "relock", reason))


def plan_stamp(
    repo: Path,
    template: Path,
    manifest: Manifest,
    installed: str,
    *,
    force: bool = False,
) -> UpgradePlan:
    """Write the stamp alone, the step the ``install-template`` skill takes last
    after ``upgrade --no-stamp``. Accepts ``local`` files awaiting a write in
    each checkout after the merge. Otherwise refuses while ``check`` reports
    anything but the stamp behind, since a stamp that overstates makes the
    next upgrade skip the repo, unless ``force``."""
    report: RepoReport = check_repo(repo, template, manifest, installed)
    plan = UpgradePlan(repo=report.path, release=installed, template=template.resolve())
    if (refusal := _newer_stamp(report, installed)) is not None:
        plan.refused = refusal
        return plan
    for f in report.files:
        if not f.current and f.status != "local":
            plan.actions.append(Action(f.path, "skip", _skip_reason(f)))
    ruff = report.ruff
    if ruff is not None and ruff.status == "differs":
        detail = ruff.detail or f"rev {ruff.rev}, locked {', '.join(ruff.locked)}"
        plan.actions.append(Action("uv.lock (ruff)", "skip", detail))
    behind = [a.path for a in plan.actions]
    if behind and not force:
        plan.refused = (
            f"check still reports {', '.join(behind)} behind the template; "
            "finish the upgrade first, or pass --force"
        )
        return plan
    if (error := _plan_stamp_write(plan, report, installed)) is not None:
        plan.refused = error
    elif behind and plan.stamp is not None and report.stamp.version != installed:
        plan.stamp_reason += f" (forced past {len(behind)} file(s))"
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
        if (error := stamp_error(section)) is not None:
            raise ValueError(f"tool.{name} {error}")
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
        if start is None:
            # A table written by hand, often to hold omit before the first
            # stamp: the comment goes directly above it, below any of the repo's
            lines.insert(at, STAMP_COMMENT)
            end += 1
            at += 1
            inside = _in_strings(lines)
        elif lines[start:at] != [STAMP_COMMENT]:
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


def relock(root: Path, version: str) -> str | None:
    """Relock ruff to exactly ``version``; the error, or None on success."""
    command = relock_command(version).split()
    try:
        result = subprocess.run(command, cwd=root, capture_output=True, text=True)
    except FileNotFoundError:
        return "uv is not on PATH"
    if result.returncode != 0:
        lines = (result.stderr or result.stdout).strip().splitlines()
        return lines[-1] if lines else f"exit {result.returncode}"
    return None


def apply(plan: UpgradePlan) -> None:
    """Write the plan. Every file, the stamped ``pyproject.toml`` included, was
    computed by ``plan_upgrade``, so a failure there writes nothing. A relock
    runs first; when it fails, its row becomes a skip naming the command to run,
    and the stamp is held back with it."""
    root = Path(plan.repo)
    if plan.relock is not None and (error := relock(root, plan.relock)):
        command = relock_command(plan.relock)
        plan.actions = [
            Action(a.path, "skip", f"run `{command}`: {error}")
            if a.action == "relock"
            else a
            for a in plan.actions
        ]
        if plan.stamp is not None:
            plan.contents.pop("pyproject.toml", None)
            plan.stamp_reason = f"held back: the ruff relock failed ({error})"
            plan.stamp = None
    for path, content in plan.contents.items():
        destination = root / path
        existed = destination.exists()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content)
        source = plan.template / path if plan.template is not None else None
        if not existed and source is not None and source.exists():
            shutil.copymode(source, destination)
