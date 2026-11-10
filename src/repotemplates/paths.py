"""Where this install's template and version come from."""

from __future__ import annotations

import importlib.metadata
from pathlib import Path

__all__ = ["template_root", "version"]

PACKAGE_DIR = Path(__file__).resolve().parent
# src/repotemplates -> the repo root, when running from a checkout
CHECKOUT_DIR = PACKAGE_DIR.parent.parent


def _shipped() -> Path:
    return PACKAGE_DIR / "template"


def _in_checkout() -> bool:
    return not _shipped().is_dir() and (CHECKOUT_DIR / "VERSION").is_file()


def template_root() -> Path:
    """The template this install ships.

    A wheel carries it as package data (``repotemplates/template``). An editable
    install from a checkout does not, so it reads the checkout's ``template/``.
    """
    if _shipped().is_dir():
        return _shipped()
    if _in_checkout() and (CHECKOUT_DIR / "template").is_dir():
        return CHECKOUT_DIR / "template"
    raise FileNotFoundError("no template found: the install ships no template/")


def version() -> str:
    """The installed release.

    A checkout reads ``VERSION`` itself: an editable install's metadata keeps the
    version from its last sync, which goes stale when stanza bumps ``VERSION``.
    """
    if _in_checkout():
        return (CHECKOUT_DIR / "VERSION").read_text().strip()
    return importlib.metadata.version("repotemplates")
