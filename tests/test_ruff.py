"""The ruff-pre-commit rev and the locked ruff: check reports them, upgrade keeps
them equal, and stamp writes the stamp alone."""

from __future__ import annotations

import tomllib
from collections.abc import Callable
from pathlib import Path

import pytest
from conftest import stamp, write
from test_classes import PRECOMMIT as PRECOMMIT_TEXT
from test_classes import bump

from repotemplates import upgrade
from repotemplates.check import check_repo
from repotemplates.manifest import Manifest
from repotemplates.render import render_repo
from repotemplates.ruff import (
    PRECOMMIT,
    in_range,
    locked_ruff,
    relock_command,
    ruff_report,
    ruff_specs,
    set_rev,
)
from repotemplates.upgrade import apply, plan_stamp, plan_upgrade

MakeRepo = Callable[..., Path]
# The fixture template's rev
TEMPLATE_REV = "v0.17.3"


def lock(*versions: str) -> str:
    rows = "".join(
        f'[[package]]\nname = "ruff"\nversion = "{v}"\n'
        'source = { registry = "https://pypi.org/simple" }\n\n'
        for v in versions
    )
    return f"version = 1\n\n{rows}"


def precommit(rev: str) -> str:
    return bump(PRECOMMIT_TEXT, "v0.17.1", rev)


@pytest.fixture
def ruff_template(template: Path) -> Path:
    write(template, PRECOMMIT, precommit(TEMPLATE_REV))
    return template


def ruff_repo(
    make_repo: MakeRepo, rev: str, locked: str | None, name: str = "r"
) -> Path:
    repo = make_repo(name)
    write(repo, PRECOMMIT, precommit(rev))
    if locked is not None:
        write(repo, "uv.lock", lock(locked))
    return repo


@pytest.fixture
def relocks(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record relocks instead of running uv."""
    calls: list[str] = []

    def fake(root: Path, version: str) -> str | None:
        calls.append(version)
        write(root, "uv.lock", lock(version))
        return None

    monkeypatch.setattr(upgrade, "relock", fake)
    return calls


def rev_in(repo: Path) -> str | None:
    text = (repo / PRECOMMIT).read_text()
    return next(
        (line.split(":", 1)[1].strip() for line in text.splitlines() if "rev:" in line),
        None,
    )


# --- the rule ---------------------------------------------------------------


@pytest.mark.parametrize("locked", ["0.17.1", "0.17.4"])
def test_local_precommit_keeps_rev_and_lock_equal(
    make_repo: MakeRepo,
    ruff_template: Path,
    manifest: Manifest,
    relocks: list[str],
    locked: str,
) -> None:
    repo = make_repo("local-precommit", ignore=f"{PRECOMMIT}\n")
    write(repo, "uv.lock", lock(locked))
    plan = plan_upgrade(repo, ruff_template, manifest, "0.2.0")
    assert plan.complete
    apply(plan)
    target = "0.17.3" if locked == "0.17.1" else locked
    assert rev_in(repo) == f"v{target}"
    assert locked_ruff(repo) == (target,)
    assert relocks == ([target] if locked != target else [])
    assert check_repo(repo, ruff_template, manifest, "0.2.0").current


def test_lock_and_rev_behind_move_to_the_template(
    make_repo: MakeRepo,
    ruff_template: Path,
    manifest: Manifest,
    relocks: list[str],
) -> None:
    repo = ruff_repo(make_repo, "v0.17.1", "0.17.1")
    report = check_repo(repo, ruff_template, manifest, "0.2.0")
    assert report.ruff is not None
    assert report.ruff.status == "same" and report.ruff.target == "0.17.3"
    plan = plan_upgrade(repo, ruff_template, manifest, "0.2.0")
    by_path = {a.path: a for a in plan.actions}
    assert by_path[PRECOMMIT].action == "write"
    assert by_path["uv.lock"].action == "relock"
    assert relock_command("0.17.3") in by_path["uv.lock"].reason
    assert plan.relock == "0.17.3" and plan.complete
    apply(plan)
    assert relocks == ["0.17.3"]
    assert rev_in(repo) == "v0.17.3" and locked_ruff(repo) == ("0.17.3",)
    assert check_repo(repo, ruff_template, manifest, "0.2.0").current


def test_lock_newer_than_the_template_leads_the_rev(
    make_repo: MakeRepo,
    ruff_template: Path,
    manifest: Manifest,
    relocks: list[str],
) -> None:
    # Dependabot moved the lock past the template; the rev was left behind
    repo = ruff_repo(make_repo, "v0.17.1", "0.17.4")
    report = check_repo(repo, ruff_template, manifest, "0.2.0")
    assert report.ruff is not None
    assert report.ruff.status == "differs" and report.ruff.target == "0.17.4"
    assert not report.current
    plan = plan_upgrade(repo, ruff_template, manifest, "0.2.0")
    assert "uv.lock" not in {a.path for a in plan.actions}
    apply(plan)
    assert relocks == []
    # Ahead of the template's rev, and equal to the lock
    assert rev_in(repo) == "v0.17.4"
    assert check_repo(repo, ruff_template, manifest, "0.2.0").current


def test_lock_and_rev_that_differ_are_reported_and_relocked(
    make_repo: MakeRepo,
    ruff_template: Path,
    manifest: Manifest,
    relocks: list[str],
) -> None:
    # A rev copied from the template, with the lock left behind
    repo = ruff_repo(make_repo, TEMPLATE_REV, "0.17.1")
    report = check_repo(repo, ruff_template, manifest, "0.2.0")
    assert report.ruff is not None and report.ruff.status == "differs"
    assert not report.current
    out = render_repo(report)
    assert "ruff rev vs uv.lock" in out
    assert "differs (rev v0.17.3, locked 0.17.1)" in out
    assert relock_command("0.17.3") in out
    as_dict = report.to_dict()["ruff"]
    assert isinstance(as_dict, dict) and as_dict["status"] == "differs"
    plan = plan_upgrade(repo, ruff_template, manifest, "0.2.0")
    actions = {a.path: a.action for a in plan.actions}
    assert actions[PRECOMMIT] == "keep" and actions["uv.lock"] == "relock"
    apply(plan)
    assert relocks == ["0.17.3"]
    assert check_repo(repo, ruff_template, manifest, "0.2.0").current


def test_rev_ahead_of_the_lock_follows_it(
    make_repo: MakeRepo, ruff_template: Path, manifest: Manifest
) -> None:
    repo = ruff_repo(make_repo, "v0.17.5", "0.17.4")
    plan = plan_upgrade(repo, ruff_template, manifest, "0.2.0")
    assert {a.path: a.action for a in plan.actions}[PRECOMMIT] == "write"
    assert plan.relock is None
    apply(plan)
    assert rev_in(repo) == "v0.17.4"


def test_a_range_that_excludes_the_template_holds_the_stamp(
    make_repo: MakeRepo, ruff_template: Path, manifest: Manifest
) -> None:
    repo = ruff_repo(make_repo, "v0.16.5", "0.16.5")
    text = stamp("0.1.0") + '\n[dependency-groups]\ndev = ["ruff>=0.16,<0.17"]\n'
    write(repo, "pyproject.toml", text)
    report = ruff_report(repo, ruff_template)
    assert report is not None and report.target == "0.16.5"
    assert "outside the repo's ruff range" in report.detail
    plan = plan_upgrade(repo, ruff_template, manifest, "0.2.0")
    skip = next(a for a in plan.actions if a.path == "uv.lock (ruff)")
    assert skip.action == "skip" and plan.stamp is None and plan.relock is None


def test_a_failed_relock_names_the_command_and_holds_the_stamp(
    make_repo: MakeRepo,
    ruff_template: Path,
    manifest: Manifest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_uv(root: Path, version: str) -> str | None:
        return "uv is not on PATH"

    monkeypatch.setattr(upgrade, "relock", no_uv)
    repo = ruff_repo(make_repo, TEMPLATE_REV, "0.17.1")
    write(repo, "pyproject.toml", stamp("0.1.0"))
    plan = plan_upgrade(repo, ruff_template, manifest, "0.2.0")
    assert plan.stamp == "0.2.0"
    apply(plan)
    row = next(a for a in plan.actions if a.path == "uv.lock")
    assert row.action == "skip" and relock_command("0.17.3") in row.reason
    assert plan.stamp is None and not plan.complete
    assert "relock failed" in plan.stamp_reason
    data = tomllib.loads((repo / "pyproject.toml").read_text())
    assert data["tool"]["repotemplates"]["version"] == "0.1.0"


def test_unlocked_repo_is_not_drift(
    make_repo: MakeRepo, ruff_template: Path, manifest: Manifest
) -> None:
    repo = ruff_repo(make_repo, TEMPLATE_REV, None)
    report = check_repo(repo, ruff_template, manifest, "0.2.0")
    assert report.ruff is not None and report.ruff.status == "unlocked"
    assert report.current


def test_no_precommit_means_no_ruff_row(
    make_repo: MakeRepo, ruff_template: Path, manifest: Manifest
) -> None:
    assert check_repo(make_repo("bare"), ruff_template, manifest, "0.2.0").ruff is None


# --- helpers ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("version", "specs", "expected"),
    [
        ("0.17.3", [">=0.17,<0.18"], True),
        ("0.18.0", [">=0.17,<0.18"], False),
        ("0.17.3", ["~=0.17.0"], True),
        ("0.18.0", ["~=0.17.0"], False),
        ("0.17.3", ["==0.17.*"], True),
        ("0.17.3", ["!=0.17.3"], False),
        ("0.17.3", [], True),
        ("0.17.3", [">=0.17", "<0.17.2"], False),
        ("0.17.3", ["@ git+https://x"], None),
    ],
)
def test_in_range(version: str, specs: list[str], expected: bool | None) -> None:
    assert in_range(version, specs) is expected


def test_ruff_specs_read_every_list(tmp_path: Path) -> None:
    write(
        tmp_path,
        "pyproject.toml",
        '[project]\ndependencies = ["ruff>=0.1"]\n'
        "[project.optional-dependencies]\n"
        "lint = [\"ruff[x] <1 ; python_version>'3'\"]\n"
        "[dependency-groups]\n"
        'dev = ["ruff>=0.17,<0.18", "ruffle>=1", {include-group = "a"}]\n',
    )
    assert ruff_specs(tmp_path) == [">=0.1", "<1", ">=0.17,<0.18"]


def test_set_rev_keeps_quotes_and_comments() -> None:
    text = bump(PRECOMMIT_TEXT, "rev: v0.17.1", "rev: 'v0.17.1'  # pinned")
    assert "rev: 'v0.17.4'  # pinned" in set_rev(text, "0.17.4")


def test_locked_ruff_lists_every_version(tmp_path: Path) -> None:
    write(tmp_path, "uv.lock", lock("0.17.4", "0.9.10"))
    assert locked_ruff(tmp_path) == ("0.9.10", "0.17.4")
    assert locked_ruff(tmp_path / "nothing") == ()


# --- stamp ------------------------------------------------------------------


def test_stamp_refuses_while_files_are_behind(
    make_repo: MakeRepo, ruff_template: Path, manifest: Manifest
) -> None:
    repo = ruff_repo(make_repo, TEMPLATE_REV, "0.17.1")
    write(repo, "pyproject.toml", stamp("0.1.0"))
    plan = plan_stamp(repo, ruff_template, manifest, "0.2.0")
    assert plan.refused is not None and "uv.lock (ruff)" in plan.refused
    forced = plan_stamp(repo, ruff_template, manifest, "0.2.0", force=True)
    assert forced.refused is None and forced.stamp == "0.2.0"
    assert "forced past 1 file(s)" in forced.stamp_reason


def test_stamp_writes_and_renames(
    make_repo: MakeRepo, ruff_template: Path, manifest: Manifest
) -> None:
    repo = ruff_repo(make_repo, TEMPLATE_REV, "0.17.3")
    write(
        repo,
        "pyproject.toml",
        stamp("0.1.0", table="proj-template")
        .replace('version = "0.1.0"\n', 'version = "0.1.0"\nomit = ["a.yml"]\n')
        .replace(
            "[tool.", "# proj-template release stamp, set by proj-init.sh\n[tool."
        ),
    )
    plan = plan_stamp(repo, ruff_template, manifest, "0.2.0")
    assert plan.refused is None and plan.stamp_reason == "0.1.0 -> 0.2.0"
    apply(plan)
    text = (repo / "pyproject.toml").read_text()
    data = tomllib.loads(text)
    assert data["tool"]["repotemplates"] == {"version": "0.2.0", "omit": ["a.yml"]}
    assert "proj-template" not in data["tool"]
    assert upgrade.STAMP_COMMENT in text
    again = plan_stamp(repo, ruff_template, manifest, "0.2.0")
    assert again.stamp is None and again.stamp_reason == "already 0.2.0"


def test_stamp_refuses_a_newer_stamp(
    make_repo: MakeRepo, ruff_template: Path, manifest: Manifest
) -> None:
    plan = plan_stamp(
        make_repo("new", version="0.3.0"), ruff_template, manifest, "0.2.0"
    )
    assert plan.refused is not None and "newer than this release" in plan.refused
