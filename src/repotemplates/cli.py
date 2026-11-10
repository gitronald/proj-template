"""The repotemplates command line.

``check``, ``upgrade``, ``init``, ``path``, and ``version`` are defined here;
``skill``, ``install``, and ``doc`` come from :func:`pkgskills.register`, which
mounts them from :data:`repotemplates.host.HOST`.
"""

from __future__ import annotations

import json
import subprocess
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from pkgskills import register

from repotemplates import paths
from repotemplates.check import check_fleet, check_repo
from repotemplates.host import HOST
from repotemplates.manifest import load_manifest
from repotemplates.render import render_fleet, render_repo, render_upgrade
from repotemplates.upgrade import apply, dirty, plan_upgrade
from repotemplates.versions import is_prerelease

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


@app.command()
def upgrade(
    repo: Annotated[Path, typer.Argument(help="Repo to upgrade (default: .).")] = Path(
        "."
    ),
    dry_run: Annotated[
        bool, typer.Option(help="Print what would change, and write nothing.")
    ] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Print JSON.")] = False,
    allow_dirty: Annotated[
        bool,
        typer.Option(help="Write over tracked files with uncommitted changes."),
    ] = False,
    prerelease: Annotated[
        bool,
        typer.Option(help="Apply this release even though it is a prerelease."),
    ] = False,
) -> None:
    """Apply the mechanical part of a template upgrade.

    Rewrites only the template-owned files that check shows hold nothing of the
    repo's own (an earlier release's copy, or pins behind the template), leaves
    the rest and says why, and stamps this release once nothing is left. Exits 0
    when the repo ends current, 1 when files were left for the install-template
    skill, 2 on a usage error or a refusal.
    """
    if not repo.is_dir():
        raise typer.BadParameter(f"not a directory: {repo}")
    installed = paths.version()
    plan = plan_upgrade(repo, paths.template_root(), load_manifest(), installed)
    if is_prerelease(installed) and not prerelease and plan.refused is None:
        # A checkout or an alpha install would stamp consumers with a release
        # that never shipped. A dry run still shows the plan.
        note = f"{installed} is a prerelease; pass --prerelease to apply it anyway"
        if dry_run:
            plan.stamp_reason += f" ({note})"
        else:
            plan.refused = note
    writes = [*plan.contents, *(["pyproject.toml"] if plan.stamp else [])]
    if plan.refused is None and not dry_run and not allow_dirty:
        if changed := dirty(Path(plan.repo), writes):
            plan.refused = (
                f"uncommitted changes in {', '.join(changed)}; commit them first, "
                "or pass --allow-dirty"
            )
    if plan.refused is None and not dry_run:
        apply(plan)
    if as_json:
        typer.echo(json.dumps({**plan.to_dict(), "dry_run": dry_run}, indent=2))
    else:
        typer.echo(render_upgrade(plan, dry_run=dry_run))
    if plan.refused is not None:
        raise typer.Exit(2)
    if not plan.complete:
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


class Deps(StrEnum):
    dependabot = "dependabot"
    renovate = "renovate"


@app.command()
def init(
    dest: Annotated[
        Path,
        typer.Argument(
            help="Directory to create. Its basename becomes the project name.",
            show_default=False,
        ),
    ],
    license_key: Annotated[
        str, typer.Option("--license", help="License key, e.g. mit or apache-2.0.")
    ] = "mit",
    deps: Annotated[
        Deps | None,
        typer.Option(help="Dependency-update automation (asks on a terminal)."),
    ] = None,
) -> None:
    """Scaffold a new repo from the template this release ships.

    Runs the release's own init.sh on its own template/, so the new repo is
    stamped with this release. The curl-to-bash path in the README runs the same
    script from GitHub.
    """
    script = paths.scripts_root() / "init.sh"
    argv = [
        "bash",
        str(script),
        "--license",
        license_key,
        "--template-dir",
        str(paths.template_root()),
        "--template-version",
        paths.version(),
    ]
    if deps is not None:
        argv += ["--deps", deps.value]
    code = subprocess.run([*argv, str(dest)]).returncode
    if code != 0:
        raise typer.Exit(code)


@app.command()
def version() -> None:
    """Print the installed release."""
    typer.echo(paths.version())


register(app, HOST)


def main() -> None:
    app(prog_name="repotemplates")
