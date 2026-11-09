"""The repotemplates command line."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from repotemplates import paths
from repotemplates.check import check_fleet, check_repo
from repotemplates.manifest import load_manifest
from repotemplates.render import render_fleet, render_repo

__all__ = ["main"]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repotemplates",
        description="Check repos against the repotemplates template.",
    )
    parser.add_argument(
        "--version", action="version", version=f"repotemplates {paths.version()}"
    )
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")

    check = commands.add_parser(
        "check",
        help="compare a repo's template-owned files with the template (read-only)",
        description=(
            "Report a repo's template stamp and how its template-owned files compare "
            "with this release's template and every earlier release. Exits 0 when "
            "everything is current, 1 when anything differs, 2 on a usage error."
        ),
    )
    check.add_argument("repo", nargs="?", type=Path, help="repo to check (default: .)")
    check.add_argument(
        "--repos-dir", type=Path, help="check every clone directly under this directory"
    )
    check.add_argument(
        "--all",
        action="store_true",
        help="with --repos-dir, include repos with no stamp",
    )
    check.add_argument(
        "--include-archived",
        action="store_true",
        help="with --repos-dir, include *-archive repos",
    )
    fmt = check.add_mutually_exclusive_group()
    fmt.add_argument(
        "--json",
        action="store_true",
        help="print JSON: an object for one repo, an array for --repos-dir",
    )
    fmt.add_argument("--markdown", action="store_true", help="print Markdown tables")

    commands.add_parser("version", help="print the installed release")
    return parser


def _check(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    repo: Path | None = args.repo
    repos_dir: Path | None = args.repos_dir
    if repo is not None and repos_dir is not None:
        parser.error("check takes a repo or --repos-dir, not both")
    if repos_dir is None and (args.all or args.include_archived):
        parser.error("--all and --include-archived need --repos-dir")
    target = repos_dir or repo or Path(".")
    if not target.is_dir():
        parser.error(f"not a directory: {target}")

    template, manifest, installed = (
        paths.template_root(),
        load_manifest(),
        paths.version(),
    )
    if repos_dir is not None:
        reports = check_fleet(
            repos_dir,
            template,
            manifest,
            installed,
            include_unstamped=args.all,
            include_archived=args.include_archived,
        )
        if args.json:
            print(json.dumps([r.to_dict() for r in reports], indent=2))
        else:
            print(render_fleet(reports, markdown=args.markdown))
        return 0 if all(r.current for r in reports) else 1

    report = check_repo(target, template, manifest, installed)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(render_repo(report, markdown=args.markdown))
    return 0 if report.current else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command == "version":
        print(paths.version())
        return 0
    return _check(args, parser)


if __name__ == "__main__":
    sys.exit(main())
