"""Where this install's template and version come from."""

from __future__ import annotations

import importlib.metadata
from pathlib import Path

__all__ = ["scripts_root", "template_root", "version"]

PACKAGE_DIR = Path(__file__).resolve().parent
# src/repotemplates -> the repo root, when running from a checkout
CHECKOUT_DIR = PACKAGE_DIR.parent.parent


def _shipped() -> Path:
    return PACKAGE_DIR / "template"


def _in_checkout() -> bool:
    return not _shipped().is_dir() and (CHECKOUT_DIR / "VERSION").is_file()


def _data_dir(name: str) -> Path:
    """A directory the wheel ships as package data, or the checkout's copy.

    A wheel carries it under the package (``repotemplates/<name>``). An editable
    install from a checkout does not, so it reads the checkout's ``<name>/``.
    """
    if (PACKAGE_DIR / name).is_dir():
        return PACKAGE_DIR / name
    if _in_checkout() and (CHECKOUT_DIR / name).is_dir():
        return CHECKOUT_DIR / name
    raise FileNotFoundError(f"no {name}/ found: the install ships none")


def template_root() -> Path:
    """The template this install ships."""
    return _data_dir("template")


def scripts_root() -> Path:
    """The scaffold scripts this install ships: ``init.sh`` and the Renovate one."""
    return _data_dir("scripts")


def version() -> str:
    """The installed release.

    A checkout reads ``VERSION`` itself: an editable install's metadata keeps the
    version from its last sync, which goes stale when stanza bumps ``VERSION``.
    """
    if _in_checkout():
        return (CHECKOUT_DIR / "VERSION").read_text().strip()
    return importlib.metadata.version("repotemplates")
