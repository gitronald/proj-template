"""upgrade: what it rewrites, what it leaves, and when it stamps."""

from __future__ import annotations

import json
import os
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
    add_worktree,
    stamp,
    write,
)
from test_classes import WORKFLOW, bump
from typer.testing import CliRunner

from repotemplates import paths
from repotemplates.check import check_repo
from repotemplates.cli import app
from repotemplates.manifest import SETTINGS_HOOKS, Manifest
from repotemplates.upgrade import (
    STAMP_COMMENT,
    apply,
    plan_stamp,
    plan_upgrade,
    set_stamp,
)

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


def test_newer_prerelease_stamp_is_refused(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    # Its status reads "alpha", not "ahead", so the guard compares versions
    repo = make_repo("alpha", version="0.3.0a0")
    plan = plan_upgrade(repo, template, manifest, "0.2.0")
    assert plan.refused is not None and plan.stamp is None


def test_prerelease_install_takes_an_older_stamp(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    # 0.2.1 is newer than every stable release the manifest knows, but older
    # than the prerelease installed
    repo = make_repo("patch", version="0.2.1")
    plan = plan_upgrade(repo, template, manifest, "0.3.0a0")
    assert plan.refused is None and plan.stamp == "0.3.0a0"


@pytest.mark.parametrize("stamp", [True, False])
def test_no_pyproject_is_not_complete(
    make_repo: MakeRepo, template: Path, manifest: Manifest, stamp: bool
) -> None:
    # --no-stamp too: the skill could not write the stamp later either
    repo = make_repo("bare", version=None)
    plan = plan_upgrade(repo, template, manifest, "0.2.0", stamp=stamp)
    assert plan.stamp is None and not plan.complete
    assert plan.stamp_reason == "no pyproject.toml to stamp"


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (
            '[project]\nname = "x"\n\n[tool.repotemplates]\nversion = "0.1.0"\n',
            '[project]\nname = "x"\n\n'
            f'{STAMP_COMMENT}\n[tool.repotemplates]\nversion = "0.2.0"\n',
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
            f"# our own note\n{STAMP_COMMENT}\n"
            '[tool.repotemplates]\nversion = "0.2.0"\n',
        ),
        (
            "# our own note\n# proj-template release stamp, set by proj-init.sh\n"
            '[tool.proj-template]\nversion = "0.1.0"\n',
            f"# our own note\n{STAMP_COMMENT}\n"
            '[tool.repotemplates]\nversion = "0.2.0"\n',
        ),
        (
            '# our release stamp, keep\n[tool.repotemplates]\nversion = "0.1.0"\n',
            f"# our release stamp, keep\n{STAMP_COMMENT}\n"
            '[tool.repotemplates]\nversion = "0.2.0"\n',
        ),
        (
            "[tool.repotemplates]  # ours\nversion='0.2.0'  # pinned\n",
            f"{STAMP_COMMENT}\n"
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


def test_current_stamp_in_another_format_gains_only_the_comment(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    repo = make_repo("terse", version="0.2.0")
    text = (repo / "pyproject.toml").read_text()
    (repo / "pyproject.toml").write_text(
        text.replace('version = "0.2.0"', "version='0.2.0'  # pinned")
    )
    plan = plan_upgrade(repo, template, manifest, "0.2.0")
    assert plan.stamp == "0.2.0" and "comment refreshed" in plan.stamp_reason
    assert "version='0.2.0'  # pinned" in plan.contents["pyproject.toml"]
    apply(plan)
    again = plan_upgrade(repo, template, manifest, "0.2.0")
    assert again.stamp is None and again.stamp_reason == "already 0.2.0"


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


@pytest.mark.parametrize(
    ("before", "after"),
    [
        # A header inside a multi-line string is text
        (
            "[project]\ndescription = '''\n[tool.repotemplates]\n"
            'version = "0.1.0"\n\'\'\'\n\n[tool.repotemplates]\nversion = "0.1.0"\n',
            "[project]\ndescription = '''\n[tool.repotemplates]\n"
            "version = \"0.1.0\"\n'''\n\n"
            f'{STAMP_COMMENT}\n[tool.repotemplates]\nversion = "0.2.0"\n',
        ),
        (
            '[project]\nx = """a\n[tool.repotemplates]\\""""\n\n'
            '[tool.repotemplates]\nversion = "0.1.0"\n',
            '[project]\nx = """a\n[tool.repotemplates]\\""""\n\n'
            f'{STAMP_COMMENT}\n[tool.repotemplates]\nversion = "0.2.0"\n',
        ),
        # Header and key spelled with quotes
        (
            '[ tool . "repotemplates" ]\n"version" = "0.1.0"\n',
            f'{STAMP_COMMENT}\n[ tool . "repotemplates" ]\nversion = "0.2.0"\n',
        ),
        # Both tables: the old one goes, the new one is read and kept
        (
            '[tool.repotemplates]\nversion = "0.1.0"\n\n'
            '[tool.proj-template]\nversion = "0.0.1"\n\n[tool.ruff]\n',
            f'{STAMP_COMMENT}\n[tool.repotemplates]\nversion = "0.2.0"\n'
            "\n[tool.ruff]\n",
        ),
        (
            "# proj-template release stamp, set by proj-init.sh\n"
            '[tool.proj-template]\nversion = "0.0.1"\n\n'
            '[tool.repotemplates]\nversion = "0.1.0"\n',
            f'{STAMP_COMMENT}\n[tool.repotemplates]\nversion = "0.2.0"\n',
        ),
        # CRLF line endings stay CRLF
        (
            '[project]\r\nname = "x"\r\n\r\n[tool.repotemplates]\r\nversion = "0.1.0"'
            "\r\n",
            '[project]\r\nname = "x"\r\n\r\n'
            f'{STAMP_COMMENT}\r\n[tool.repotemplates]\r\nversion = "0.2.0"\r\n',
        ),
        # A current stamp written inline is left as it is
        (
            '[tool]\nrepotemplates = {version = "0.2.0", omit = ["a.yml"]}\n',
            '[tool]\nrepotemplates = {version = "0.2.0", omit = ["a.yml"]}\n',
        ),
    ],
)
def test_set_stamp_reads_toml_as_toml(before: str, after: str) -> None:
    assert set_stamp(before, "0.2.0") == after
    assert set_stamp(after, "0.2.0") == after


@pytest.mark.parametrize(
    ("text", "error"),
    [
        ('[tool]\nrepotemplates = {version = "0.1.0"}\n', "stamp it by hand"),
        ('[tool]\nrepotemplates.version = "0.1.0"\n', "stamp it by hand"),
        ('tool = {proj-template = {version = "0.2.0"}}\n', "stamp it by hand"),
        ("[tool]\nrepotemplates = 1\n", "is not a table"),
        ('[tool.repotemplates]\nversion = "0.1.0"\nomit = [1]\n', "list of paths"),
        ('[tool.repotemplates]\nversion = "0.1.0"\nomit = "a.yml"\n', "list of paths"),
        (
            # Once a multi-line string's header was taken for the stamp, this
            # reached an AttributeError the planner does not catch
            "[project]\nx = '''\n[tool.repotemplates]\nversion = \"0.1.0\"\n'''\n"
            "[tool]\nrepotemplates = 1\n",
            "is not a table",
        ),
    ],
)
def test_set_stamp_refuses_what_it_cannot_stamp(text: str, error: str) -> None:
    with pytest.raises(ValueError, match=error):
        set_stamp(text, "0.2.0")


def test_malformed_omit_is_left_unstamped(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    repo = make_repo("omit", version="0.1.0")
    text = (repo / "pyproject.toml").read_text()
    (repo / "pyproject.toml").write_text(text + "omit = [1]\n")
    plan = plan_upgrade(repo, template, manifest, "0.2.0")
    assert plan.stamp is None and not plan.complete


def test_first_stamp_keeps_a_hand_written_omit(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    repo = make_repo("first", version=None, hook=None)
    write(repo, "pyproject.toml", f'[tool.repotemplates]\nomit = ["{HOOK}"]\n')
    plan = plan_stamp(repo, template, manifest, "0.2.0")
    assert plan.refused is None and plan.stamp == "0.2.0"
    assert plan.stamp_reason == "none -> 0.2.0"
    apply(plan)
    assert (repo / "pyproject.toml").read_text() == (
        f'{STAMP_COMMENT}\n[tool.repotemplates]\nversion = "0.2.0"\nomit = ["{HOOK}"]\n'
    )


def test_stamp_still_refuses_a_file_behind(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    repo = make_repo("behind", version=None, hook=OLD_HOOK)
    write(repo, "pyproject.toml", '[tool.repotemplates]\nomit = ["a.yml"]\n')
    plan = plan_stamp(repo, template, manifest, "0.2.0")
    assert plan.refused is not None and HOOK in plan.refused


def test_worktree_stamps_with_current_files_in_the_main_checkout(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    repo = make_repo("ignores", version="0.1.0", ignore=".claude/\n")
    tree = add_worktree(repo, ".gitignore", "pyproject.toml")
    plan = plan_stamp(tree, template, manifest, "0.2.0")
    assert plan.refused is None and plan.stamp == "0.2.0"


@pytest.mark.parametrize("linked", [False, True], ids=["main", "linked"])
def test_first_adoption_stamps_with_local_files(
    make_repo: MakeRepo, template: Path, manifest: Manifest, linked: bool
) -> None:
    repo = make_repo("first", version=None, hook=None, hooks=None, ignore=".claude/\n")
    write(repo, "pyproject.toml", '[project]\nname = "demo"\n')
    tree = add_worktree(repo, ".gitignore", "pyproject.toml") if linked else repo
    plan = plan_stamp(tree, template, manifest, "0.2.0")
    assert plan.refused is None and plan.stamp == "0.2.0"
    assert plan.complete and not plan.actions
    apply(plan)
    assert stamp_of(tree) == "0.2.0"
    assert not (repo / ".claude").exists()
    assert not (tree / ".claude").exists()


@pytest.mark.parametrize("linked", [False, True], ids=["main", "linked"])
def test_upgrade_writes_local_files_in_its_checkout(
    make_repo: MakeRepo, template: Path, manifest: Manifest, linked: bool
) -> None:
    write(template, TEST_YML, WORKFLOW)
    repo = make_repo("local", hook=None, hooks=None, ignore=f".claude/\n{TEST_YML}\n")
    tree = add_worktree(repo, ".gitignore", "pyproject.toml") if linked else repo
    plan = plan_upgrade(tree, template, manifest, "0.2.0", stamp=False)
    assert plan.complete and plan.stamp is None
    assert {a.path: a.action for a in plan.actions} == {
        HOOK: "write",
        SETTINGS_HOOKS: "write",
        TEST_YML: "write",
    }
    assert all(a.reason.startswith("local:") for a in plan.actions)
    assert not (tree / ".claude").exists()
    apply(plan)
    for path in (HOOK, SETTINGS, TEST_YML):
        assert (tree / path).read_bytes() == (template / path).read_bytes()
        if linked:
            assert not (repo / path).exists()
    assert check_repo(tree, template, manifest, "0.2.0").current


def test_upgrade_copies_template_modes_for_local_files(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    (template / HOOK).chmod(0o755)
    (template / SETTINGS).chmod(0o644)
    repo = make_repo("local-modes", hook=None, hooks=None, ignore=".claude/\n")
    plan = plan_upgrade(repo, template, manifest, "0.2.0")
    assert all(a.reason.startswith("local:") for a in plan.actions)
    apply(plan)
    assert os.access(repo / HOOK, os.X_OK)
    assert not os.access(repo / SETTINGS, os.X_OK)


def test_upgrade_preserves_existing_file_modes(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    (template / HOOK).chmod(0o755)
    (template / SETTINGS).chmod(0o644)
    repo = make_repo("existing-modes", hook=OLD_HOOK, hooks=OLD_HOOKS)
    (repo / HOOK).chmod(0o640)
    (repo / SETTINGS).chmod(0o600)
    plan = plan_upgrade(repo, template, manifest, "0.2.0")
    apply(plan)
    assert (repo / HOOK).read_bytes() == NEW_HOOK
    assert json.loads((repo / SETTINGS).read_text())["hooks"] == NEW_HOOKS
    assert (repo / HOOK).stat().st_mode & 0o777 == 0o640
    assert (repo / SETTINGS).stat().st_mode & 0o777 == 0o600


def test_first_adoption_still_refuses_a_stale_main_checkout_hook(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    repo = make_repo("stale", hook=OLD_HOOK, hooks=None, ignore=".claude/\n")
    tree = add_worktree(repo, ".gitignore", "pyproject.toml")
    files = {f.path: f for f in check_repo(tree, template, manifest, "0.2.0").files}
    assert (files[HOOK].status, files[HOOK].source) == (
        "matches",
        str(repo.resolve()),
    )
    assert files[SETTINGS_HOOKS].status == "local"
    plan = plan_stamp(tree, template, manifest, "0.2.0")
    assert plan.refused is not None and HOOK in plan.refused
    assert [a.path for a in plan.actions] == [HOOK]
    assert not plan.contents


@pytest.mark.parametrize("linked", [False, True], ids=["main", "linked"])
def test_stamp_refuses_missing_files_that_are_not_ignored(
    make_repo: MakeRepo, template: Path, manifest: Manifest, linked: bool
) -> None:
    repo = make_repo("missing", hook=None, hooks=None)
    tree = add_worktree(repo, "pyproject.toml") if linked else repo
    report = check_repo(tree, template, manifest, "0.2.0")
    assert {f.status for f in report.files} == {"missing"}
    plan = plan_stamp(tree, template, manifest, "0.2.0")
    assert plan.refused is not None and HOOK in plan.refused
    assert {a.path for a in plan.actions} == {HOOK, SETTINGS_HOOKS}
    assert not plan.contents


def test_worktree_leaves_a_behind_main_checkout_file_alone(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    repo = make_repo("ignores-old", version="0.1.0", hook=OLD_HOOK, ignore=".claude/\n")
    tree = add_worktree(repo, ".gitignore", "pyproject.toml")
    plan = plan_upgrade(tree, template, manifest, "0.2.0", stamp=False)
    skip = next(a for a in plan.actions if a.path == HOOK)
    assert skip.action == "skip" and "fix it there" in skip.reason
    assert str(repo.resolve()) in skip.reason
    assert not plan.contents and not (tree / HOOK).exists()
    refused = plan_stamp(tree, template, manifest, "0.2.0").refused
    assert refused is not None and HOOK in refused


def test_worktree_names_stale_pins_in_a_main_checkout_file(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    # A pinned file the repo ignores, current but for its pins
    write(template, TEST_YML, WORKFLOW)
    repo = make_repo("ignores-pins", ignore=f"{TEST_YML}\n")
    write(repo, TEST_YML, bump(WORKFLOW, "aaaa  # v7.0.1", "dddd  # v6.0.0"))
    tree = add_worktree(repo, ".gitignore", "pyproject.toml", HOOK, SETTINGS)
    plan = plan_upgrade(tree, template, manifest, "0.2.0", stamp=False)
    skip = next(a for a in plan.actions if a.path == TEST_YML)
    assert skip.action == "skip"
    assert skip.reason.startswith("current, with pins behind; raise them by hand")
    assert "fix it there" in skip.reason


def kept(make_repo: MakeRepo, name: str, release: str) -> Path:
    repo = make_repo(name, version=None, hook=b"echo mine\n")
    write(
        repo,
        "pyproject.toml",
        f'[tool.repotemplates]\nversion = "0.1.0"\nkeep = {{"{HOOK}" = "{release}"}}\n',
    )
    return repo


def test_kept_file_is_left_and_stamped(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    repo = kept(make_repo, "kept", "0.2.0")
    plan = plan_upgrade(repo, template, manifest, "0.2.0")
    action = next(a for a in plan.actions if a.path == HOOK)
    assert (action.action, action.reason) == ("keep", "kept as of v0.2.0")
    assert plan.complete and plan.stamp == "0.2.0"
    assert plan_stamp(repo, template, manifest, "0.2.0").refused is None
    apply(plan)
    assert (repo / HOOK).read_bytes() == b"echo mine\n"
    data = tomllib.loads((repo / "pyproject.toml").read_text())
    assert data["tool"]["repotemplates"]["keep"] == {HOOK: "0.2.0"}


def test_kept_file_behind_holds_the_stamp(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    repo = kept(make_repo, "kept-old", "0.1.0")
    plan = plan_upgrade(repo, template, manifest, "0.2.0")
    skip = next(a for a in plan.actions if a.path == HOOK)
    assert skip.action == "skip" and "reviewed against v0.1.0" in skip.reason
    assert plan.stamp is None
    refused = plan_stamp(repo, template, manifest, "0.2.0").refused
    assert refused is not None and HOOK in refused


def test_kept_pinned_file_with_pins_behind_is_left(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    write(template, TEST_YML, WORKFLOW)
    repo = make_repo("kept-pins", version=None)
    write(
        repo,
        "pyproject.toml",
        f'[tool.repotemplates]\nversion = "0.2.0"\nkeep = {{"{TEST_YML}" = "0.2.0"}}\n',
    )
    custom = bump(WORKFLOW, "aaaa  # v7.0.1", "dddd  # v6.0.0") + "      - run: extra\n"
    write(repo, TEST_YML, custom)
    plan = plan_upgrade(repo, template, manifest, "0.2.0")
    skip = next(a for a in plan.actions if a.path == TEST_YML)
    assert skip.action == "skip" and "pins behind" in skip.reason
    assert TEST_YML not in plan.contents


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


def test_command_stamps_local_files_and_check_keeps_the_reminder(
    scaffolded: Path,
) -> None:
    (scaffolded / HOOK).unlink()
    (scaffolded / SETTINGS).unlink()
    code, out = run("stamp", str(scaffolded), "--prerelease")
    assert code == 0, out
    code, out = run("check", str(scaffolded), "--json")
    assert code == 1
    report = json.loads(out)
    assert report["current"] is False
    rows = {f["path"]: f for f in report["files"]}
    for path in (HOOK, SETTINGS_HOOKS):
        assert rows[path]["status"] == "local"
        assert rows[path]["detail"] == [
            "ignored; write it in each checkout after the merge"
        ]


def test_command_no_stamp_leaves_the_stamp(scaffolded: Path) -> None:
    # Current but for the stamp, which upgrade would otherwise move
    code, out = run("upgrade", str(scaffolded), "--prerelease", "--no-stamp", "--json")
    assert code == 0, out
    plan = json.loads(out)
    assert plan["complete"] is True and plan["stamp"] is None
    assert "--no-stamp" in plan["stamp_reason"]
    assert stamp_of(scaffolded) == "0.1.0"


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
