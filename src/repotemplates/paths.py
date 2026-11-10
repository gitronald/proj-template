"""Where this install's template and version come from."""

from __future__ import annotations

import importlib.metadata
import subprocess
from pathlib import Path

__all__ = ["scripts_root", "stray_files", "template_root", "version"]

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


def stray_files(root: Path) -> list[str]:
    """Untracked or ignored files under a checkout's ``root``, as git lists them.

    A wheel's copy is exactly the tracked files (CI checks it), but a checkout's
    ``template/`` can hold a stray ``uv.lock`` or ``.venv`` that ``init.sh
    --template-dir`` would copy into every new project. Empty for a shipped copy,
    and when git cannot answer. ``__pycache__`` is left out: ``init.sh`` skips it.
    """
    if not _in_checkout() or not root.resolve().is_relative_to(CHECKOUT_DIR):
        return []
    try:
        result = subprocess.run(
            ["git", "ls-files", "--others", "--directory", "--", str(root)],
            cwd=CHECKOUT_DIR,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return []
    if result.returncode != 0:
        return []
    return [p for p in result.stdout.splitlines() if "__pycache__" not in p]


def version() -> str:
    """The installed release.

    A checkout reads ``VERSION`` itself: an editable install's metadata keeps the
    version from its last sync, which goes stale when stanza bumps ``VERSION``.
    """
    if _in_checkout():
        return (CHECKOUT_DIR / "VERSION").read_text().strip()
    return importlib.metadata.version("repotemplates")
