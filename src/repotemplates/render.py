"""Plain-text and Markdown tables for check reports."""

from __future__ import annotations

from collections.abc import Sequence

from repotemplates.check import KINDS, FileReport, RepoReport, StampReport
from repotemplates.ruff import PRECOMMIT, RuffReport, relock_command
from repotemplates.upgrade import UpgradePlan

__all__ = ["render_fleet", "render_repo", "render_upgrade"]


def _table(
    headers: Sequence[str], rows: Sequence[Sequence[str]], markdown: bool
) -> str:
    if markdown:
        lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
        lines += ["| " + " | ".join(row) + " |" for row in rows]
        return "\n".join(lines)
    widths = [max(len(r[i]) for r in [headers, *rows]) for i in range(len(headers))]
    return "\n".join(
        "  ".join(cell.ljust(w) for cell, w in zip(row, widths, strict=True)).rstrip()
        for row in [headers, *rows]
    )


def _status(f: FileReport) -> str:
    if f.status == "matches":
        text = f"matches v{f.release}"
    elif f.status == "retired":
        text = f"retired, matches v{f.release}"
    else:
        text = f.status
    if f.pins not in (None, "same"):
        text += f", pins {f.pins}"
    return text


def _stamp(s: StampReport) -> str:
    if s.version is None:
        return s.status
    if s.status in ("behind", "ahead"):
        return f"{s.version}, {s.status} {s.latest}"
    return f"{s.version}, {s.status}"


def _label(key: str) -> str:
    return key.replace("#hooks", " (hooks)")


def _detail(f: FileReport) -> str:
    parts = [f"read from {f.source}"] if f.source else []
    if f.detail:
        parts.append(f"lacks {', '.join(f.detail)}")
    if f.waived:
        parts.append(f"waived {', '.join(f.waived)} (tracked)")
    return "; ".join(parts)


def _ruff_status(r: RuffReport) -> str:
    locked = ", ".join(r.locked) or "none"
    return f"{r.status} (rev {r.rev}, locked {locked})"


def _ruff_detail(r: RuffReport) -> str:
    if r.detail:
        return r.detail
    if r.status == "differs" and r.target is not None:
        steps = [f"rev to v{r.target}"] if r.rev.removeprefix("v") != r.target else []
        if r.relock:
            steps.append(f"`{relock_command(r.target)}`")
        return "the rev equals the locked ruff: " + ", ".join(steps)
    if r.status == "unlocked":
        return "no ruff in uv.lock"
    return ""


def render_repo(report: RepoReport, markdown: bool = False) -> str:
    rows = [
        [_label(f.path), _status(f), f.git or "-", _detail(f)] for f in report.files
    ]
    if report.ruff is not None:
        row = [f"{PRECOMMIT} (ruff rev vs uv.lock)", _ruff_status(report.ruff)]
        rows.append([*row, "-", _ruff_detail(report.ruff)])
    settings = ", ".join(f"{path} {state}" for path, state in report.settings.items())
    head = [
        f"repo: {report.name} ({report.path})",
        f"stamp: {_stamp(report.stamp)}",
        f"claude settings: {settings}",
        "",
    ]
    if markdown:
        head = [f"- {line}" if line else line for line in head]
    body = (
        _table(["file", "status", "git", "detail"], rows, markdown)
        if rows
        else "no template-owned files"
    )
    return "\n".join(head) + "\n" + body


def _summary(files: Sequence[FileReport]) -> str:
    if not files:
        return "-"
    statuses = list(dict.fromkeys(_status(f) for f in files))
    return "; ".join(statuses)


def render_fleet(reports: Sequence[RepoReport], markdown: bool = False) -> str:
    if not reports:
        return "no repos to check"
    rows: list[list[str]] = []
    for r in reports:
        settings_git = " / ".join(
            f"{'local ' if path.endswith('local.json') else ''}{state}"
            for path, state in r.settings.items()
            if state != "absent"
        )
        rows.append(
            [
                r.name,
                r.stamp.version or "-",
                r.stamp.status,
                *(_summary([f for f in r.files if f.kind == k]) for k in KINDS),
                r.ruff.status if r.ruff is not None else "-",
                settings_git or "absent",
            ]
        )
    headers = [
        "repo",
        "stamp",
        "stamp status",
        "hook scripts",
        "hook entries",
        "pinned",
        "config",
        "ignore",
        "ruff rev",
        "settings git",
    ]
    return _table(headers, rows, markdown)


def render_upgrade(plan: UpgradePlan, dry_run: bool = False) -> str:
    head = [f"repo: {plan.repo}", f"release: {plan.release}"]
    if dry_run:
        head.append("dry run: nothing written")
    if plan.refused is not None:
        return "\n".join([*head, f"refused: {plan.refused}"])
    rows = [[_label(a.path), a.action, a.reason] for a in plan.actions]
    stamp = f"stamp: {'write ' if plan.stamp else ''}{plan.stamp_reason}"
    body = _table(["file", "action", "reason"], rows, False) if rows else "no files"
    return "\n".join([*head, stamp, "", body])
