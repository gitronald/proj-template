from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from repotemplates import paths
from repotemplates.manifest import (
    SETTINGS_HOOKS,
    DirSource,
    build_manifest,
    fingerprint,
    hooks_block_digest,
    load_manifest,
    release_tags,
)
from repotemplates.versions import is_prerelease, sort_key

ROOT = Path(__file__).resolve().parent.parent


def _tags() -> list[str]:
    result = subprocess.run(
        ["git", "tag", "--list", "v*"], cwd=ROOT, capture_output=True, text=True
    )
    return result.stdout.split() if result.returncode == 0 else []


def test_shipped_template_has_both_classes() -> None:
    prints = fingerprint(DirSource(paths.template_root()))
    assert ".claude/hooks/lint-typecheck.sh" in prints
    assert SETTINGS_HOOKS in prints


def test_manifest_loads_and_is_ordered() -> None:
    manifest = load_manifest()
    keys = [key for r in manifest.releases if (key := sort_key(r)) is not None]
    assert len(keys) == len(manifest.releases)
    assert keys == sorted(keys)
    for by_release in manifest.files.values():
        assert set(by_release) <= set(manifest.releases)


needs_tags = pytest.mark.skipif(not _tags(), reason="no release tags (shallow clone)")


@needs_tags
def test_manifest_is_fresh() -> None:
    """The committed manifest equals one regenerated from the tags before VERSION.

    Fails on dev after a release, until scripts/build_manifest.py is rerun. The
    release itself, on main, still passes: its own tag is not expected.
    """
    committed = (ROOT / "src/repotemplates/data/manifest.json").read_text()
    version = (ROOT / "VERSION").read_text().strip()
    assert build_manifest(ROOT, before=version).to_json() == committed, (
        "manifest is stale: run uv run python scripts/build_manifest.py"
    )


@needs_tags
def test_release_tags_before_a_version() -> None:
    tags = release_tags(ROOT, before="0.4.0")
    assert "0.4.0" not in tags
    limit = sort_key("0.4.0")
    assert limit is not None
    assert tags and all((k := sort_key(t)) is not None and k < limit for t in tags)


def test_hooks_block_digest() -> None:
    assert hooks_block_digest(b'{"permissions": {}}') is None
    assert hooks_block_digest(b'{"hooks": {"a": 1}, "x": 2}') == hooks_block_digest(
        b'{"hooks":{"a":1}}'
    )
    with pytest.raises(ValueError):
        hooks_block_digest(b"[]")


def test_versions() -> None:
    assert sort_key("v0.12.0") == sort_key("0.12.0")
    key_a, key_final = sort_key("0.12.1a0"), sort_key("0.12.1")
    assert key_a is not None and key_final is not None and key_a < key_final
    assert is_prerelease("0.12.1rc2")
    assert not is_prerelease("0.12.1")
    assert sort_key("unknown") is None
