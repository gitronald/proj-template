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

from repotemplates.check import RAISABLE_PINS, FileReport, RepoReport, check_repo
from repotemplates.classes import merge_pinned
from repotemplates.manifest import SETTINGS, SETTINGS_HOOKS, Manifest, file_path

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
    if report.stamp.status == "ahead":
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


# A table or an array-of-tables header; an array's name keeps its brackets, so
# ``[[tool.repotemplates]]`` is never taken for the stamp table
_HEADER = re.compile(r"^\s*(?P<head>\[\[?[^\[\]]+\]\]?)\s*(#.*)?$")


def _tables(lines: list[str]) -> list[tuple[int, str]]:
    return [
        (i, _table_name(m["head"]))
        for i, line in enumerate(lines)
        if (m := _HEADER.match(line))
    ]


def _table_name(head: str) -> str:
    if head.startswith("[["):
        return head
    return head.strip("[]").strip()


def _value(line: str) -> object:
    """The value a ``version = ...`` line sets, or None when it does not parse."""
    try:
        return tomllib.loads(line).get("version")
    except tomllib.TOMLDecodeError:
        return None


def set_stamp(text: str, release: str) -> str:
    """``pyproject.toml`` with ``[tool.repotemplates] version`` set to ``release``.

    Renames an old ``[tool.proj-template]`` table, and adds the table after
    ``[project.scripts]`` (or at the end) when the repo has neither.
    """
    lines = text.split("\n")
    tables = _tables(lines)
    names = [name for _, name in tables]
    version_line = f'version = "{release}"'
    for old in ("tool.repotemplates", "tool.proj-template"):
        if old not in names:
            continue
        at = tables[names.index(old)][0]
        end = next((i for i, _ in tables if i > at), len(lines))
        if old != "tool.repotemplates":
            lines[at] = "[tool.repotemplates]"
        top = at
        while top > 0 and lines[top - 1].lstrip().startswith("#"):
            top -= 1
        start = next(
            (i for i in range(top, at) if _TEMPLATE_COMMENT.match(lines[i])), None
        )
        if start is not None and lines[start:at] != [STAMP_COMMENT]:
            lines[start:at] = [STAMP_COMMENT]
            end -= at - start - 1
            at = start + 1
        for i in range(at + 1, end):
            if re.match(r"^\s*version\s*=", lines[i]):
                if _value(lines[i]) != release:
                    lines[i] = version_line
                break
        else:
            lines.insert(at + 1, version_line)
        break
    else:
        block = [STAMP_COMMENT, "[tool.repotemplates]", version_line, ""]
        if "project.scripts" in names:
            at = tables[names.index("project.scripts")][0]
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
    stamp = tomllib.loads(out).get("tool", {}).get("repotemplates", {})
    if stamp.get("version") != release:
        raise ValueError("could not set the stamp in pyproject.toml")
    return out


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
