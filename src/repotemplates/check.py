"""Compare a repo's template-owned files with the template. Read-only."""

from __future__ import annotations

import subprocess
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path

from repotemplates.classes import (
    CONFIG,
    GITIGNORE,
    IGNORE,
    PINNED,
    attribute_gaps,
    compare_pins,
    ignore_gaps,
)
from repotemplates.manifest import (
    SETTINGS,
    SETTINGS_HOOKS,
    DirSource,
    Manifest,
    file_digest,
    file_path,
    fingerprint,
)
from repotemplates.ruff import RuffReport, ruff_report
from repotemplates.versions import is_prerelease, sort_key

__all__ = [
    "CLAUDE_SETTINGS",
    "KINDS",
    "RAISABLE_PINS",
    "FileReport",
    "RepoReport",
    "StampReport",
    "check_fleet",
    "check_repo",
    "latest_release",
]

# The stamp table, and the name it had before the rename in 0.12.0.
STAMP_TABLES = ("repotemplates", "proj-template")
CLAUDE_SETTINGS = (SETTINGS, ".claude/settings.local.json")
# The file classes, in report order
KINDS = ("hook-script", "hook-entries", "pinned", "config", "ignore")
# Pin verdicts that leave a pinned file behind the template. upgrade raises
# the raisable ones; ``differs`` (a pin that is not a version) needs a person.
RAISABLE_PINS = ("behind", "mixed")
STALE_PINS = (*RAISABLE_PINS, "differs")
DEPENDABOT = ".github/dependabot.yml"
RENOVATE = (".github/renovate.json", ".github/workflows/renovate.yml")


@dataclass(frozen=True)
class StampReport:
    """``status``: latest, behind, ahead, alpha, unknown, unreadable, or missing.

    ``omit`` is the stamp table's list of template files the repo leaves out on
    purpose.
    """

    version: str | None
    table: str | None
    status: str
    latest: str | None
    omit: tuple[str, ...] = ()


@dataclass(frozen=True)
class FileReport:
    """``status``: current, matches, retired, one-off, partial, missing, omitted,
    or unreadable.

    ``matches`` and ``retired`` name a release: the newest one the file equals.
    ``retired`` is a path the template no longer ships. ``partial`` is an ignore
    file missing some of the template's rules, listed in ``detail``. ``omitted``
    is a file the repo leaves out by design: declared in the stamp's ``omit``, or
    the Dependabot or Renovate file of a repo that uses the other.
    ``pins`` is set for a pinned file: same, ahead, behind, mixed, or differs.
    ``waived`` lists an ignore file's template rules the repo leaves out because
    it tracks paths they would ignore.
    """

    path: str
    kind: str
    status: str
    release: str | None = None
    git: str | None = None
    pins: str | None = None
    detail: tuple[str, ...] = ()
    waived: tuple[str, ...] = ()

    @property
    def current(self) -> bool:
        return self.status in ("current", "omitted") and self.pins not in STALE_PINS


@dataclass(frozen=True)
class RepoReport:
    name: str
    path: str
    stamp: StampReport
    files: list[FileReport] = field(default_factory=list)
    settings: dict[str, str] = field(default_factory=dict)
    # The ruff-pre-commit rev against the locked ruff, a row of its own: a rev
    # that differs from the lock is drift even when every pin is current
    ruff: RuffReport | None = None

    @property
    def current(self) -> bool:
        ruff_ok = self.ruff is None or self.ruff.status != "differs"
        return (
            self.stamp.status == "latest"
            and all(f.current for f in self.files)
            and ruff_ok
        )

    def to_dict(self) -> dict[str, object]:
        out = asdict(self)
        out["current"] = self.current
        return out


def latest_release(manifest: Manifest, installed: str) -> str | None:
    """The newest stable release this install knows: its own, or a tagged one."""
    candidates = list(manifest.releases)
    if not is_prerelease(installed):
        candidates.append(installed)
    keyed = [
        (key, v) for v in candidates if (key := sort_key(v)) and not is_prerelease(v)
    ]
    return max(keyed)[1] if keyed else None


def read_stamp(repo: Path, latest: str | None) -> StampReport:
    pyproject = repo / "pyproject.toml"
    if not pyproject.is_file():
        return StampReport(None, None, "missing", latest)
    try:
        data = tomllib.loads(pyproject.read_text())
    except (OSError, tomllib.TOMLDecodeError, UnicodeDecodeError):
        return StampReport(None, None, "unreadable", latest)
    tool = data.get("tool", {})
    if not isinstance(tool, dict):
        return StampReport(None, None, "unreadable", latest)
    for table in STAMP_TABLES:
        if table not in tool:
            continue
        # A stamp table with no string version is malformed, not missing
        section = tool[table]
        value = section.get("version") if isinstance(section, dict) else None
        if not isinstance(value, str):
            return StampReport(None, f"tool.{table}", "unreadable", latest)
        omit = section.get("omit", [])
        if not isinstance(omit, list) or not all(isinstance(o, str) for o in omit):
            return StampReport(value, f"tool.{table}", "unreadable", latest)
        status = _stamp_status(value, latest)
        return StampReport(value, f"tool.{table}", status, latest, tuple(omit))
    return StampReport(None, None, "missing", latest)


def _stamp_status(value: str, latest: str | None) -> str:
    key = sort_key(value)
    if key is None:
        return "unknown"
    if is_prerelease(value):
        return "alpha"
    latest_key = sort_key(latest) if latest else None
    if latest_key is None or key == latest_key:
        return "latest"
    return "behind" if key < latest_key else "ahead"


def _git(repo: Path, *args: str) -> int:
    try:
        return subprocess.run(["git", *args], cwd=repo, capture_output=True).returncode
    except FileNotFoundError:
        # No git on PATH: every query fails, so git_state reports "no git"
        return 127


def git_state(repo: Path, path: str) -> str:
    """tracked, ignored, untracked, absent, or no git."""
    if not (repo / path).exists():
        return "absent"
    if _git(repo, "rev-parse", "--git-dir") != 0:
        return "no git"
    if _git(repo, "ls-files", "--error-unmatch", "--", path) == 0:
        return "tracked"
    if _git(repo, "check-ignore", "-q", "--", path) == 0:
        return "ignored"
    return "untracked"


def _kind(key: str) -> str:
    if key == SETTINGS_HOOKS:
        return "hook-entries"
    if key in PINNED:
        return "pinned"
    if key in CONFIG:
        return "config"
    if key in IGNORE:
        return "ignore"
    return "hook-script"


def _repo_digest(repo: Path, key: str) -> tuple[str | None, bool]:
    """The repo's digest for ``key``, and whether the file could be read."""
    try:
        raw = DirSource(repo).read(file_path(key))
    except OSError:
        return None, False
    if raw is None:
        return None, True
    try:
        return file_digest(key, raw), True
    except ValueError:
        return None, False


def _ordered(keys: set[str]) -> list[str]:
    return sorted(keys, key=lambda k: (KINDS.index(_kind(k)), k))


def omitted(repo: Path, declared: tuple[str, ...]) -> set[str]:
    """Paths the repo leaves out by design: declared, or the other updater's files.

    A repo on Renovate has no use for the Dependabot file, and one on Dependabot
    none for the Renovate pair, so the file present names the choice.
    """
    out = set(declared)
    if (repo / DEPENDABOT).is_file():
        out.update(RENOVATE)
    elif any((repo / path).is_file() for path in RENOVATE):
        out.add(DEPENDABOT)
    return out


def _pins(repo: Path, template: Path, key: str) -> str | None:
    if key not in PINNED:
        return None
    try:
        ours = (repo / key).read_text()
        theirs = (template / key).read_text()
    except (OSError, UnicodeDecodeError):
        return None
    return compare_pins(ours, theirs)


def _ignore_report(repo: Path, template: Path, path: str, skip: set[str]) -> FileReport:
    git = git_state(repo, path)
    present = (repo / path).is_file()
    if not present and path in skip:
        return FileReport(path, "ignore", "omitted", git=git)
    # git_state asked already when the file is there
    if git == "no git" or (not present and _git(repo, "rev-parse", "--git-dir")):
        # The rules are checked by asking git, so a directory that is not a repo
        # cannot answer
        return FileReport(path, "ignore", "unreadable", git="no git")
    text = (template / path).read_text()
    waived: list[str] = []
    try:
        if path == GITIGNORE:
            gaps, waived = ignore_gaps(repo, text)
        else:
            gaps = attribute_gaps(repo, text)
    except OSError:
        return FileReport(path, "ignore", "unreadable", git=git)
    status = "current" if not gaps else "partial" if present else "missing"
    return FileReport(
        path, "ignore", status, git=git, detail=tuple(gaps), waived=tuple(waived)
    )


def check_repo(
    repo: Path, template: Path, manifest: Manifest, installed: str
) -> RepoReport:
    repo = repo.resolve()
    shipped = fingerprint(DirSource(template))
    latest = latest_release(manifest, installed)
    stamp = read_stamp(repo, latest)
    skip = omitted(repo, stamp.omit)
    files: list[FileReport] = []
    for key in _ordered(set(shipped) | set(manifest.files)):
        value, readable = _repo_digest(repo, key)
        path, kind = file_path(key), _kind(key)
        git = git_state(repo, path)
        if not readable:
            files.append(FileReport(key, kind, "unreadable", git=git))
        elif value is None:
            if key in shipped:
                status = "omitted" if path in skip or key in skip else "missing"
                files.append(FileReport(key, kind, status, git=git))
        elif value == shipped.get(key):
            pins = _pins(repo, template, key)
            files.append(FileReport(key, kind, "current", git=git, pins=pins))
        elif (release := manifest.match(key, value)) is not None:
            status = "matches" if key in shipped else "retired"
            pins = _pins(repo, template, key) if key in shipped else None
            files.append(FileReport(key, kind, status, release, git, pins))
        else:
            files.append(FileReport(key, kind, "one-off", git=git))
    for path in IGNORE:
        if (template / path).is_file():
            files.append(_ignore_report(repo, template, path, skip))
    settings = {path: git_state(repo, path) for path in CLAUDE_SETTINGS}
    ruff = ruff_report(repo, template)
    return RepoReport(repo.name, str(repo), stamp, files, settings, ruff)


def is_repo(path: Path) -> bool:
    return path.is_dir() and (path / ".git").exists()


def check_fleet(
    repos_dir: Path,
    template: Path,
    manifest: Manifest,
    installed: str,
    *,
    include_unstamped: bool = False,
    include_archived: bool = False,
) -> list[RepoReport]:
    """Check every clone directly under ``repos_dir``.

    Skips ``*-archive`` repos and repos with no stamp unless asked for them.
    """
    reports: list[RepoReport] = []
    for child in sorted(repos_dir.iterdir()):
        if not is_repo(child):
            continue
        if child.name.endswith("-archive") and not include_archived:
            continue
        report = check_repo(child, template, manifest, installed)
        if report.stamp.status == "missing" and not include_unstamped:
            continue
        reports.append(report)
    return reports
