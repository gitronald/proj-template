"""Fingerprints of the template-owned files, and the per-release manifest.

A fingerprint maps each template-owned key to a content digest. Two classes of
file are template-owned so far:

- Claude hook scripts, ``.claude/hooks/*.sh``, compared by exact content.
- Claude hook entries, the ``hooks`` block of ``.claude/settings.json``, compared
  as normalized JSON so other keys and formatting do not count.

The manifest records the fingerprint of every release tag, so ``check`` can name
the release a file matches. It holds tagged releases only; the template an
install ships is fingerprinted at run time, so a release never has to list itself.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Protocol

from repotemplates.versions import sort_key

__all__ = [
    "HOOKS_DIR",
    "SETTINGS",
    "SETTINGS_HOOKS",
    "DirSource",
    "GitTagSource",
    "Manifest",
    "build_manifest",
    "digest",
    "fingerprint",
    "hooks_block_digest",
    "load_manifest",
]

SCHEMA = 1
HOOKS_DIR = ".claude/hooks"
SETTINGS = ".claude/settings.json"
SETTINGS_HOOKS = f"{SETTINGS}#hooks"


class Source(Protocol):
    def read(self, path: str) -> bytes | None: ...

    def list_dir(self, path: str) -> list[str]: ...


@dataclass(frozen=True)
class DirSource:
    """Files under a directory on disk: a shipped template or a consumer repo."""

    root: Path

    def read(self, path: str) -> bytes | None:
        target = self.root / path
        return target.read_bytes() if target.is_file() else None

    def list_dir(self, path: str) -> list[str]:
        target = self.root / path
        if not target.is_dir():
            return []
        return sorted(p.name for p in target.iterdir() if p.is_file())


@dataclass(frozen=True)
class GitTagSource:
    """The template as committed at a tag, read without a checkout."""

    repo: Path
    ref: str
    prefix: str = "template/"

    def _git(self, *args: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(["git", *args], cwd=self.repo, capture_output=True)

    def read(self, path: str) -> bytes | None:
        result = self._git("show", f"{self.ref}:{self.prefix}{path}")
        return result.stdout if result.returncode == 0 else None

    def list_dir(self, path: str) -> list[str]:
        result = self._git(
            "ls-tree", "--name-only", self.ref, "--", f"{self.prefix}{path}/"
        )
        if result.returncode != 0:
            return []
        names = result.stdout.decode().splitlines()
        return sorted(name.rsplit("/", 1)[-1] for name in names)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hooks_block_digest(raw: bytes) -> str | None:
    """Digest of a settings file's ``hooks`` block, or None when it has none.

    Raises ValueError when the file is not a JSON object.
    """
    data: object = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("settings file is not a JSON object")
    if "hooks" not in data:
        return None
    block = json.dumps(data["hooks"], sort_keys=True, separators=(",", ":"))
    return digest(block.encode())


def fingerprint(source: Source) -> dict[str, str]:
    """Digest of every template-owned file the source has."""
    out: dict[str, str] = {}
    for name in source.list_dir(HOOKS_DIR):
        if name.endswith(".sh"):
            data = source.read(f"{HOOKS_DIR}/{name}")
            if data is not None:
                out[f"{HOOKS_DIR}/{name}"] = digest(data)
    raw = source.read(SETTINGS)
    if raw is not None:
        block = hooks_block_digest(raw)
        if block is not None:
            out[SETTINGS_HOOKS] = block
    return out


@dataclass(frozen=True)
class Manifest:
    """The fingerprint of each release, oldest release first."""

    releases: list[str]
    files: dict[str, dict[str, str]]

    def match(self, key: str, value: str) -> str | None:
        """The newest release whose copy of ``key`` has this digest."""
        by_release = self.files.get(key, {})
        for release in reversed(self.releases):
            if by_release.get(release) == value:
                return release
        return None

    def to_json(self) -> str:
        payload = {"schema": SCHEMA, "releases": self.releases, "files": self.files}
        return json.dumps(payload, indent=2) + "\n"

    @classmethod
    def from_json(cls, text: str) -> Manifest:
        payload = json.loads(text)
        if payload.get("schema") != SCHEMA:
            raise ValueError(f"unsupported manifest schema: {payload.get('schema')!r}")
        return cls(releases=list(payload["releases"]), files=dict(payload["files"]))


def load_manifest() -> Manifest:
    """The manifest this install ships."""
    text = files("repotemplates").joinpath("data/manifest.json").read_text()
    return Manifest.from_json(text)


def release_tags(repo: Path, before: str | None = None) -> list[str]:
    """Release tags in the repo, oldest first, without the leading v.

    With ``before``, only tags that sort below that version.
    """
    result = subprocess.run(
        ["git", "tag", "--list", "v*"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    limit = sort_key(before) if before else None
    keyed = [
        (key, tag)
        for tag in result.stdout.split()
        if (key := sort_key(tag)) and (limit is None or key < limit)
    ]
    return [tag.removeprefix("v") for _, tag in sorted(keyed)]


def build_manifest(repo: Path, before: str | None = None) -> Manifest:
    """Fingerprint ``template/`` at every release tag in ``repo``.

    ``before`` is the checkout's own version: its tag, once it exists, is left
    out, since an install fingerprints the template it ships at run time.
    """
    releases = release_tags(repo, before)
    by_key: dict[str, dict[str, str]] = {}
    for release in releases:
        for key, value in fingerprint(GitTagSource(repo, f"v{release}")).items():
            by_key.setdefault(key, {})[release] = value
    return Manifest(releases=releases, files=dict(sorted(by_key.items())))
