"""The repotemplates command line.

``check``, ``path``, and ``version`` are defined here; ``skill``, ``install``,
and ``doc`` come from :func:`pkgskills.register`, which mounts them from
:data:`repotemplates.host.HOST`.
"""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from pkgskills import register

from repotemplates import paths
from repotemplates.check import check_fleet, check_repo
from repotemplates.host import HOST
from repotemplates.manifest import load_manifest
from repotemplates.render import render_fleet, render_repo

__all__ = ["app", "main"]

app = typer.Typer(
    name="repotemplates",
    help="Scaffold repos from the repotemplates template and check repos against it.",
    no_args_is_help=True,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"repotemplates {paths.version()}")
        raise typer.Exit()


@app.callback()
def _root(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Print the installed release and exit.",
        ),
    ] = False,
) -> None:
    """Scaffold repos from the repotemplates template and check repos against it."""


@app.command()
def check(
    repo: Annotated[
        Path | None, typer.Argument(help="Repo to check (default: .).")
    ] = None,
    repos_dir: Annotated[
        Path | None,
        typer.Option(help="Check every clone directly under this directory."),
    ] = None,
    all_repos: Annotated[
        bool, typer.Option("--all", help="With --repos-dir, include unstamped repos.")
    ] = False,
    include_archived: Annotated[
        bool, typer.Option(help="With --repos-dir, include *-archive repos.")
    ] = False,
    as_json: Annotated[
        bool,
        typer.Option(
            "--json", help="Print JSON: an object for one repo, an array for a fleet."
        ),
    ] = False,
    markdown: Annotated[bool, typer.Option(help="Print Markdown tables.")] = False,
) -> None:
    """Compare a repo's template-owned files with the template (read-only).

    Reports the repo's template stamp and how its template-owned files compare
    with this release's template and every earlier release. Exits 0 when
    everything is current, 1 when anything differs, 2 on a usage error.
    """
    if repo is not None and repos_dir is not None:
        raise typer.BadParameter("check takes a repo or --repos-dir, not both")
    if repos_dir is None and (all_repos or include_archived):
        raise typer.BadParameter("--all and --include-archived need --repos-dir")
    if as_json and markdown:
        raise typer.BadParameter("--json and --markdown are exclusive")
    target = repos_dir or repo or Path(".")
    if not target.is_dir():
        raise typer.BadParameter(f"not a directory: {target}")

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
            include_unstamped=all_repos,
            include_archived=include_archived,
        )
        if as_json:
            typer.echo(json.dumps([r.to_dict() for r in reports], indent=2))
        else:
            typer.echo(render_fleet(reports, markdown=markdown))
        # An empty fleet is not a current one: exit 1, so a wrong path fails a script
        if not (reports and all(r.current for r in reports)):
            raise typer.Exit(1)
        return

    report = check_repo(target, template, manifest, installed)
    if as_json:
        typer.echo(json.dumps(report.to_dict(), indent=2))
    else:
        typer.echo(render_repo(report, markdown=markdown))
    if not report.current:
        raise typer.Exit(1)


class Shipped(StrEnum):
    template = "template"
    scripts = "scripts"


@app.command()
def path(
    what: Annotated[Shipped, typer.Argument(help="Which shipped directory.")],
) -> None:
    """Print the directory of the template or scripts this release ships.

    A skill body reads the template from here rather than from a checkout, so
    it applies the release that is installed.
    """
    root = paths.template_root() if what is Shipped.template else paths.scripts_root()
    typer.echo(str(root))


@app.command()
def version() -> None:
    """Print the installed release."""
    typer.echo(paths.version())


register(app, HOST)


def main() -> None:
    app(prog_name="repotemplates")
