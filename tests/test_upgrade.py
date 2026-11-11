"""upgrade: what it rewrites, what it leaves, and when it stamps."""

from __future__ import annotations

import json
import shutil
import subprocess
import tomllib
from collections.abc import Callable
from pathlib import Path

import pytest
from conftest import (
    HOOK,
    NEW_HOOK,
    NEW_HOOKS,
    OLD_HOOK,
    OLD_HOOKS,
    SETTINGS,
    stamp,
    write,
)
from test_classes import WORKFLOW, bump
from typer.testing import CliRunner

from repotemplates import paths
from repotemplates.cli import app
from repotemplates.manifest import SETTINGS_HOOKS, Manifest
from repotemplates.upgrade import STAMP_COMMENT, apply, plan_upgrade, set_stamp

MakeRepo = Callable[..., Path]
TEST_YML = ".github/workflows/test.yml"


def actions(repo: Path, template: Path, manifest: Manifest) -> dict[str, str]:
    plan = plan_upgrade(repo, template, manifest, "0.2.0")
    return {a.path: a.action for a in plan.actions}


def stamp_of(repo: Path) -> str:
    data = tomllib.loads((repo / "pyproject.toml").read_text())
    return data["tool"]["repotemplates"]["version"]


def test_earlier_release_is_rewritten_and_stamped(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    repo = make_repo("old", version="0.1.0", hook=OLD_HOOK, hooks=None)
    write(
        repo,
        SETTINGS,
        json.dumps({"permissions": {"allow": ["x"]}, "hooks": OLD_HOOKS}),
    )
    plan = plan_upgrade(repo, template, manifest, "0.2.0")
    assert {a.path: a.action for a in plan.actions} == {
        HOOK: "write",
        SETTINGS_HOOKS: "write",
    }
    assert plan.stamp == "0.2.0" and plan.complete
    apply(plan)
    assert (repo / HOOK).read_bytes() == NEW_HOOK
    settings = json.loads((repo / SETTINGS).read_text())
    assert settings == {"permissions": {"allow": ["x"]}, "hooks": NEW_HOOKS}
    assert stamp_of(repo) == "0.2.0"
    # A second run has nothing to do
    again = plan_upgrade(repo, template, manifest, "0.2.0")
    assert {a.action for a in again.actions} == {"keep"} and again.stamp is None


def test_one_off_is_left_and_the_stamp_holds(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    repo = make_repo("custom", version="0.1.0", hook=b"echo mine\n", hooks=OLD_HOOKS)
    plan = plan_upgrade(repo, template, manifest, "0.2.0")
    assert {a.path: a.action for a in plan.actions} == {
        HOOK: "skip",
        SETTINGS_HOOKS: "write",
    }
    assert plan.stamp is None and not plan.complete
    assert "left at 0.1.0" in plan.stamp_reason
    apply(plan)
    assert (repo / HOOK).read_bytes() == b"echo mine\n"
    assert stamp_of(repo) == "0.1.0"


def test_missing_file_is_left(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    repo = make_repo("bare", hook=None)
    plan = plan_upgrade(repo, template, manifest, "0.2.0")
    skip = next(a for a in plan.actions if a.path == HOOK)
    assert skip.action == "skip" and skip.reason.startswith("missing")
    assert not (repo / HOOK).exists() or (repo / HOOK).read_bytes() != NEW_HOOK


def test_pins_behind_are_raised_and_ahead_kept(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    write(template, TEST_YML, WORKFLOW)
    repo = make_repo("pins")
    repo_yml = bump(WORKFLOW, "aaaa  # v7.0.1", "dddd  # v6.0.0")
    repo_yml = bump(repo_yml, "bbbb  # v10.3.0", "cccc  # v10.3.3")
    write(repo, TEST_YML, bump(repo_yml, '"3.11", ', ""))
    plan = plan_upgrade(repo, template, manifest, "0.2.0")
    assert {a.path: a.action for a in plan.actions}[TEST_YML] == "write"
    apply(plan)
    text = (repo / TEST_YML).read_text()
    assert "checkout@aaaa  # v7.0.1" in text
    assert "setup-uv@cccc  # v10.3.3" in text
    assert '["3.12", "3.13", "3.14"]' in text
    assert actions(repo, template, manifest)[TEST_YML] == "keep"


def test_newer_stamp_is_refused(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    plan = plan_upgrade(make_repo("new", version="0.3.0"), template, manifest, "0.2.0")
    assert plan.refused is not None and "newer than this release" in plan.refused
    assert plan.actions == []


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (
            '[project]\nname = "x"\n\n[tool.repotemplates]\nversion = "0.1.0"\n',
            '[project]\nname = "x"\n\n[tool.repotemplates]\nversion = "0.2.0"\n',
        ),
        (
            "# proj-template release stamp, set by proj-init.sh and install-template; "
            'inert to consumers.\n[tool.proj-template]\nversion = "0.1.0"\n'
            "\n[tool.ruff]\n",
            f'{STAMP_COMMENT}\n[tool.repotemplates]\nversion = "0.2.0"\n'
            "\n[tool.ruff]\n",
        ),
        (
            "# Which proj-template release this repo was scaffolded from, stamped by\n"
            "# proj-init.sh and re-stamped by the install-template skill on upgrade. "
            "Inert to\n# consumers.\n"
            '[tool.proj-template]\nversion = "0.1.0"\nomit = ["a.yml"]\n'
            "\n[tool.ruff]\n",
            f'{STAMP_COMMENT}\n[tool.repotemplates]\nversion = "0.2.0"\n'
            'omit = ["a.yml"]\n\n[tool.ruff]\n',
        ),
        (
            '# our own note\n[tool.proj-template]\nversion = "0.1.0"\n',
            '# our own note\n[tool.repotemplates]\nversion = "0.2.0"\n',
        ),
        (
            "# our own note\n# proj-template release stamp, set by proj-init.sh\n"
            '[tool.proj-template]\nversion = "0.1.0"\n',
            f"# our own note\n{STAMP_COMMENT}\n"
            '[tool.repotemplates]\nversion = "0.2.0"\n',
        ),
        (
            '# our release stamp, keep\n[tool.repotemplates]\nversion = "0.1.0"\n',
            '# our release stamp, keep\n[tool.repotemplates]\nversion = "0.2.0"\n',
        ),
        (
            "[tool.repotemplates]  # ours\nversion='0.2.0'  # pinned\n",
            "[tool.repotemplates]  # ours\nversion='0.2.0'  # pinned\n",
        ),
        (
            '[project.scripts]\nx = "x:app"\n\n[tool.ruff]\nline-length = 88\n',
            '[project.scripts]\nx = "x:app"\n\n'
            "# repotemplates release stamp, set by init.sh and install-template; "
            'inert to consumers.\n[tool.repotemplates]\nversion = "0.2.0"\n\n'
            "[tool.ruff]\nline-length = 88\n",
        ),
        (
            '[project]\nname = "x"\n',
            '[project]\nname = "x"\n\n'
            "# repotemplates release stamp, set by init.sh and install-template; "
            'inert to consumers.\n[tool.repotemplates]\nversion = "0.2.0"\n',
        ),
    ],
)
def test_set_stamp(before: str, after: str) -> None:
    assert set_stamp(before, "0.2.0") == after


def test_stale_stamp_comment_is_refreshed(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    repo = make_repo("stale", version="0.2.0")
    stale = "# repotemplates release stamp, set by proj-init.sh and install-template"
    text = (repo / "pyproject.toml").read_text()
    (repo / "pyproject.toml").write_text(
        text.replace("[tool.repotemplates]", f"{stale}\n[tool.repotemplates]")
    )
    plan = plan_upgrade(repo, template, manifest, "0.2.0")
    assert plan.stamp == "0.2.0" and "comment refreshed" in plan.stamp_reason
    apply(plan)
    assert (
        f"{STAMP_COMMENT}\n[tool.repotemplates]"
        in (repo / "pyproject.toml").read_text()
    )
    again = plan_upgrade(repo, template, manifest, "0.2.0")
    assert again.stamp is None and again.stamp_reason == "already 0.2.0"


def test_current_stamp_in_another_format_is_left_alone(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    repo = make_repo("terse", version="0.2.0")
    text = (repo / "pyproject.toml").read_text()
    (repo / "pyproject.toml").write_text(
        text.replace('version = "0.2.0"', "version='0.2.0'  # pinned")
    )
    plan = plan_upgrade(repo, template, manifest, "0.2.0")
    assert plan.stamp is None and plan.stamp_reason == "already 0.2.0"


def test_old_table_at_this_release_is_renamed(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    repo = make_repo("old", version=None)
    (repo / "pyproject.toml").write_text(stamp("0.2.0", table="proj-template"))
    plan = plan_upgrade(repo, template, manifest, "0.2.0")
    assert plan.stamp == "0.2.0" and plan.stamp_reason == "already 0.2.0; table renamed"


def test_set_stamp_sees_array_tables() -> None:
    text = '[tool.repotemplates]\nother = 1\n\n[[x]]\nversion = "1"\n'
    out = tomllib.loads(set_stamp(text, "0.2.0"))
    assert out["tool"]["repotemplates"] == {"version": "0.2.0", "other": 1}
    assert out["x"] == [{"version": "1"}]


def test_unparseable_pyproject_is_left_unstamped(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    repo = make_repo("broken", version="0.1.0", hook=OLD_HOOK)
    (repo / "pyproject.toml").write_text("[tool.repotemplates\n")
    plan = plan_upgrade(repo, template, manifest, "0.2.0")
    skip = next(a for a in plan.actions if a.path == "pyproject.toml")
    assert skip.action == "skip" and "cannot set the stamp" in skip.reason
    assert plan.stamp is None and not plan.complete
    assert "pyproject.toml" not in plan.contents


def test_set_stamp_keeps_omit() -> None:
    text = '[tool.repotemplates]\nversion = "0.1.0"\nomit = ["a.yml"]\n'
    out = tomllib.loads(set_stamp(text, "0.2.0"))["tool"]["repotemplates"]
    assert out == {"version": "0.2.0", "omit": ["a.yml"]}


# --- the command ---------------------------------------------------------------


@pytest.fixture
def scaffolded(tmp_path: Path) -> Path:
    """A committed git repo holding the shipped template, stamped 0.1.0."""
    repo = tmp_path / "scaffolded"
    shutil.copytree(paths.template_root(), repo)
    (repo / "pyproject.toml").write_text('[tool.repotemplates]\nversion = "0.1.0"\n')
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com"]
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run([*git, "commit", "-qm", "init"], cwd=repo, check=True)
    return repo


def run(*argv: str) -> tuple[int, str]:
    result = CliRunner().invoke(app, list(argv))
    return result.exit_code, result.output


def test_command_dry_run_writes_nothing(scaffolded: Path) -> None:
    code, out = run("upgrade", str(scaffolded), "--dry-run", "--prerelease")
    assert code == 0, out
    assert "dry run" in out and f"0.1.0 -> {paths.version()}" in out
    assert stamp_of(scaffolded) == "0.1.0"


def test_command_stamps_a_current_repo(scaffolded: Path) -> None:
    code, out = run("upgrade", str(scaffolded), "--prerelease", "--json")
    assert code == 0, out
    assert json.loads(out)["complete"] is True
    assert stamp_of(scaffolded) == paths.version()


def test_command_refuses_dirty_tracked_files(scaffolded: Path) -> None:
    (scaffolded / "pyproject.toml").write_text(
        '[tool.repotemplates]\nversion = "0.1.0"\n# edited\n'
    )
    code, out = run("upgrade", str(scaffolded), "--prerelease")
    assert code == 2 and "uncommitted changes in pyproject.toml" in out
    assert run("upgrade", str(scaffolded), "--prerelease", "--allow-dirty")[0] == 0


def test_command_refuses_a_prerelease(
    scaffolded: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("repotemplates.cli.paths.version", lambda: "0.9.0a1")
    code, out = run("upgrade", str(scaffolded))
    assert code == 2 and "0.9.0a1 is a prerelease" in out
    assert stamp_of(scaffolded) == "0.1.0"
    # A dry run still shows the plan
    code, out = run("upgrade", str(scaffolded), "--dry-run")
    assert code == 0 and "needs" not in out and "pass --prerelease" in out
