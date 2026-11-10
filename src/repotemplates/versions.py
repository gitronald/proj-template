"""Release numbers: X.Y.Z with an optional aN, bN, or rcN, and an optional v."""

from __future__ import annotations

import re

__all__ = ["is_prerelease", "sort_key"]

_VERSION = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:(a|b|rc)(\d+))?$")
# A final release sorts after its own prereleases.
_PHASE = {"a": 0, "b": 1, "rc": 2, None: 3}

SortKey = tuple[int, int, int, int, int]


def sort_key(text: str) -> SortKey | None:
    """A key that orders releases, or None when ``text`` is not one."""
    m = _VERSION.match(text.strip())
    if m is None:
        return None
    major, minor, patch, phase, number = m.groups()
    return (int(major), int(minor), int(patch), _PHASE[phase], int(number or 0))


def is_prerelease(text: str) -> bool:
    key = sort_key(text)
    return key is not None and key[3] != _PHASE[None]
