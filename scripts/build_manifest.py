"""Regenerate the release manifest from this repo's tags.

Usage:
    uv run python scripts/build_manifest.py           # write the manifest
    uv run python scripts/build_manifest.py --check   # exit 1 when it is stale

Run on dev after each release, once its tag exists, and commit the result. The
manifest lists the tags older than VERSION: an install fingerprints the template
it ships at run time, so a release never needs an entry for itself.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from repotemplates.manifest import build_manifest

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "src" / "repotemplates" / "data" / "manifest.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check", action="store_true", help="exit 1 when the manifest is stale"
    )
    args = parser.parse_args()
    version = (ROOT / "VERSION").read_text().strip()
    text = build_manifest(ROOT, before=version).to_json()
    if args.check:
        if not MANIFEST.is_file() or MANIFEST.read_text() != text:
            print(
                "Error: the manifest is stale; "
                "run uv run python scripts/build_manifest.py",
                file=sys.stderr,
            )
            return 1
        print("manifest is current")
        return 0
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(text)
    print(f"wrote {MANIFEST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
