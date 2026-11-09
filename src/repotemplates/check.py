"""Compare a repo's template-owned files with the template. Read-only."""

from __future__ import annotations

import subprocess
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path

from repotemplates.manifest import (
    SETTINGS,
    SETTINGS_HOOKS,
    DirSource,
    Manifest,
    digest,
    fingerprint,
    hooks_block_digest,
)
from repotemplates.versions import is_prerelease, sort_key

__all__ = [
    "CLAUDE_SETTINGS",
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


@dataclass(frozen=True)
class StampReport:
    """``status``: latest, behind, ahead, alpha, unknown, unreadable, or missing."""

    version: str | None
    table: str | None
    status: str
    latest: str | None


@dataclass(frozen=True)
class FileReport:
    """``status``: current, matches, retired, one-off, missing, or unreadable.

    ``matches`` and ``retired`` name a release: the newest one the file equals.
    ``retired`` is a path the template no longer ships.
    """

    path: str
    kind: str
    status: str
    release: str | None = None
    git: str | None = None


@dataclass(frozen=True)
class RepoReport:
    name: str
    path: str
    stamp: StampReport
    files: list[FileReport] = field(default_factory=list)
    settings: dict[str, str] = field(default_factory=dict)

    @property
    def current(self) -> bool:
        return self.stamp.status == "latest" and all(
            f.status == "current" for f in self.files
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
    except (tomllib.TOMLDecodeError, UnicodeDecodeError):
        return StampReport(None, None, "unreadable", latest)
    tool = data.get("tool", {})
    for table in STAMP_TABLES:
        value = tool.get(table, {}).get("version") if isinstance(tool, dict) else None
        if isinstance(value, str):
            return StampReport(
                value, f"tool.{table}", _stamp_status(value, latest), latest
            )
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
    return subprocess.run(["git", *args], cwd=repo, capture_output=True).returncode


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
    return "hook-entries" if key == SETTINGS_HOOKS else "hook-script"


def _file_path(key: str) -> str:
    return key.split("#", 1)[0]


def _repo_digest(repo: Path, key: str) -> tuple[str | None, bool]:
    """The repo's digest for ``key``, and whether the file could be read."""
    raw = DirSource(repo).read(_file_path(key))
    if raw is None:
        return None, True
    if key != SETTINGS_HOOKS:
        return digest(raw), True
    try:
        return hooks_block_digest(raw), True
    except ValueError:
        return None, False


def _ordered(keys: set[str]) -> list[str]:
    # Hook scripts first, then the settings entries.
    return sorted(keys, key=lambda k: (k == SETTINGS_HOOKS, k))


def check_repo(
    repo: Path, template: Path, manifest: Manifest, installed: str
) -> RepoReport:
    repo = repo.resolve()
    shipped = fingerprint(DirSource(template))
    latest = latest_release(manifest, installed)
    files: list[FileReport] = []
    for key in _ordered(set(shipped) | set(manifest.files)):
        value, readable = _repo_digest(repo, key)
        path, kind = _file_path(key), _kind(key)
        git = git_state(repo, path)
        if not readable:
            files.append(FileReport(key, kind, "unreadable", git=git))
        elif value is None:
            if key in shipped:
                files.append(FileReport(key, kind, "missing", git=git))
        elif value == shipped.get(key):
            files.append(FileReport(key, kind, "current", git=git))
        elif (release := manifest.match(key, value)) is not None:
            status = "matches" if key in shipped else "retired"
            files.append(FileReport(key, kind, status, release, git))
        else:
            files.append(FileReport(key, kind, "one-off", git=git))
    settings = {path: git_state(repo, path) for path in CLAUDE_SETTINGS}
    return RepoReport(repo.name, str(repo), read_stamp(repo, latest), files, settings)


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
