"""Fixture template, manifest, and repos for the check tests.

The fake template has two releases of each file: 0.1.0 (old) and 0.2.0 (new),
with the template shipping the 0.2.0 copies.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from repotemplates.manifest import DirSource, Manifest, fingerprint

HOOK = ".claude/hooks/lint-typecheck.sh"
SETTINGS = ".claude/settings.json"
RETIRED = ".claude/hooks/retired.sh"

OLD_HOOK = b"#!/usr/bin/env bash\necho old\n"
NEW_HOOK = b"#!/usr/bin/env bash\necho new\n"
RETIRED_HOOK = b"#!/usr/bin/env bash\necho retired\n"
OLD_HOOKS = {"Stop": [{"hooks": [{"type": "command", "command": "old.sh"}]}]}
NEW_HOOKS = {
    "Stop": [{"hooks": [{"type": "command", "command": "new.sh", "timeout": 120}]}]
}


def write(root: Path, rel: str, data: bytes | str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode() if isinstance(data, str) else data)


def settings(hooks: object, **extra: object) -> str:
    return json.dumps({"hooks": hooks, **extra}, indent=2)


def stamp(version: str, table: str = "repotemplates") -> str:
    return f'[project]\nname = "demo"\n\n[tool.{table}]\nversion = "{version}"\n'


def make_tree(root: Path, hook: bytes, hooks: object) -> Path:
    write(root, HOOK, hook)
    write(root, SETTINGS, settings(hooks))
    return root


@pytest.fixture(autouse=True)
def isolated_git(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep the user's global ignores (often settings.local.json) out of git states.

    The default excludes file is $XDG_CONFIG_HOME/git/ignore, read even with no
    global config, so point XDG_CONFIG_HOME somewhere empty too.
    """
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


@pytest.fixture
def template(tmp_path: Path) -> Path:
    return make_tree(tmp_path / "template", NEW_HOOK, NEW_HOOKS)


@pytest.fixture
def manifest(tmp_path: Path) -> Manifest:
    # 0.1.0 also shipped a hook that 0.2.0 dropped
    write(make_tree(tmp_path / "r010", OLD_HOOK, OLD_HOOKS), RETIRED, RETIRED_HOOK)
    old = fingerprint(DirSource(tmp_path / "r010"))
    new = fingerprint(DirSource(make_tree(tmp_path / "r020", NEW_HOOK, NEW_HOOKS)))
    files: dict[str, dict[str, str]] = {}
    for release, prints in (("0.1.0", old), ("0.2.0", new)):
        for key, value in prints.items():
            files.setdefault(key, {})[release] = value
    return Manifest(releases=["0.1.0", "0.2.0"], files=files)


def git_init(repo: Path, *, ignore: str = "", track: tuple[str, ...] = ()) -> Path:
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    if ignore:
        write(repo, ".gitignore", ignore)
    if track:
        subprocess.run(["git", "add", "--", *track], cwd=repo, check=True)
    return repo


@pytest.fixture
def make_repo(tmp_path: Path) -> Callable[..., Path]:
    """Build a repo under tmp_path/repos/<name>."""

    def _make(
        name: str,
        *,
        version: str | None = "0.2.0",
        hook: bytes | None = NEW_HOOK,
        hooks: object = NEW_HOOKS,
        ignore: str = "",
        track: tuple[str, ...] = (),
        git: bool = True,
    ) -> Path:
        repo = tmp_path / "repos" / name
        repo.mkdir(parents=True)
        if version is not None:
            write(repo, "pyproject.toml", stamp(version))
        if hook is not None:
            write(repo, HOOK, hook)
        if hooks is not None:
            write(repo, SETTINGS, settings(hooks))
        if git:
            git_init(repo, ignore=ignore, track=track)
        return repo

    return _make


def add_worktree(repo: Path, *paths: str) -> Path:
    """Commit ``paths`` in ``repo`` and add a linked worktree beside it.

    The worktree gets the committed files only, as ``git worktree add`` gives.
    """
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com"]
    subprocess.run(["git", "add", "--", *paths], cwd=repo, check=True)
    subprocess.run([*git, "commit", "-qm", "init"], cwd=repo, check=True)
    tree = repo.parent / f"{repo.name}-wt"
    subprocess.run(["git", "worktree", "add", "-q", str(tree)], cwd=repo, check=True)
    return tree
