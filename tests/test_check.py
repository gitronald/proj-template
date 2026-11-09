from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from conftest import HOOK, NEW_HOOKS, OLD_HOOK, OLD_HOOKS, RETIRED, RETIRED_HOOK, write

from repotemplates.check import (
    FileReport,
    RepoReport,
    check_fleet,
    check_repo,
    latest_release,
)
from repotemplates.manifest import SETTINGS_HOOKS, Manifest

MakeRepo = Callable[..., Path]


def run(
    repo: Path, template: Path, manifest: Manifest, installed: str = "0.2.0"
) -> RepoReport:
    return check_repo(repo, template, manifest, installed)


def by_path(report: RepoReport) -> dict[str, FileReport]:
    return {f.path: f for f in report.files}


def test_current_repo(make_repo: MakeRepo, template: Path, manifest: Manifest) -> None:
    report = run(make_repo("fresh"), template, manifest)
    assert report.stamp.status == "latest"
    assert [(f.path, f.status) for f in report.files] == [
        (HOOK, "current"),
        (SETTINGS_HOOKS, "current"),
    ]
    assert report.current


def test_one_release_behind(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    repo = make_repo("old", version="0.1.0", hook=OLD_HOOK, hooks=OLD_HOOKS)
    report = run(repo, template, manifest)
    assert report.stamp.status == "behind"
    assert report.stamp.latest == "0.2.0"
    files = by_path(report)
    assert (files[HOOK].status, files[HOOK].release) == ("matches", "0.1.0")
    assert (files[SETTINGS_HOOKS].status, files[SETTINGS_HOOKS].release) == (
        "matches",
        "0.1.0",
    )
    assert not report.current


def test_one_off(make_repo: MakeRepo, template: Path, manifest: Manifest) -> None:
    repo = make_repo("custom", hook=b"#!/usr/bin/env bash\necho mine\n")
    files = by_path(run(repo, template, manifest))
    assert files[HOOK].status == "one-off"
    assert files[HOOK].release is None


def test_hook_entries_ignore_other_keys_and_formatting(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    repo = make_repo("extra-keys", hooks=None)
    # Same hooks as the template, keys reordered and compacted, beside other keys
    hooks = '{"Stop":[{"hooks":[{"timeout":120,"command":"new.sh","type":"command"}]}]}'
    write(repo, ".claude/settings.json", f'{{"permissions": {{}}, "hooks": {hooks}}}')
    assert by_path(run(repo, template, manifest))[SETTINGS_HOOKS].status == "current"


def test_missing_files(make_repo: MakeRepo, template: Path, manifest: Manifest) -> None:
    files = by_path(run(make_repo("bare", hook=None, hooks=None), template, manifest))
    assert files[HOOK].status == "missing"
    assert files[SETTINGS_HOOKS].status == "missing"


def test_settings_without_hooks_block(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    repo = make_repo("no-hooks", hooks=None)
    write(repo, ".claude/settings.json", '{"permissions": {}}')
    assert by_path(run(repo, template, manifest))[SETTINGS_HOOKS].status == "missing"


def test_unreadable_settings(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    repo = make_repo("broken", hooks=None)
    write(repo, ".claude/settings.json", "{not json")
    assert by_path(run(repo, template, manifest))[SETTINGS_HOOKS].status == "unreadable"


def test_retired_hook(make_repo: MakeRepo, template: Path, manifest: Manifest) -> None:
    repo = make_repo("leftover")
    write(repo, RETIRED, RETIRED_HOOK)
    report = run(repo, template, manifest)
    retired = by_path(report)[RETIRED]
    assert (retired.status, retired.release) == ("retired", "0.1.0")
    assert not report.current


def test_repo_own_hook_is_not_reported(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    repo = make_repo("own-hook")
    write(repo, ".claude/hooks/mine.sh", b"echo mine\n")
    report = run(repo, template, manifest)
    assert ".claude/hooks/mine.sh" not in by_path(report)
    assert report.current


def test_settings_ignored(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    report = run(make_repo("ignored", ignore=".claude/\n"), template, manifest)
    assert report.settings == {
        ".claude/settings.json": "ignored",
        ".claude/settings.local.json": "absent",
    }
    assert {f.git for f in report.files} == {"ignored"}
    # Git state is information, not drift: the template itself ignores .claude/
    assert report.current


def test_settings_tracked_and_untracked(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    repo = make_repo("tracked", track=(".claude/settings.json",))
    write(repo, ".claude/settings.local.json", "{}")
    report = run(repo, template, manifest)
    assert report.settings == {
        ".claude/settings.json": "tracked",
        ".claude/settings.local.json": "untracked",
    }
    assert by_path(report)[HOOK].git == "untracked"


def test_no_git(make_repo: MakeRepo, template: Path, manifest: Manifest) -> None:
    report = run(make_repo("plain", git=False), template, manifest)
    assert report.settings[".claude/settings.json"] == "no git"


def test_stamp_statuses(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    cases = {
        "0.2.1a0": "alpha",
        "0.3.0": "ahead",
        "unknown": "unknown",
        "0.1.0": "behind",
    }
    for version, status in cases.items():
        repo = make_repo(f"stamp-{version}", version=version)
        assert run(repo, template, manifest).stamp.status == status, version


def test_legacy_stamp_table(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    repo = make_repo("legacy", version=None)
    write(repo, "pyproject.toml", '[tool.proj-template]\nversion = "0.2.0"\n')
    stamp = run(repo, template, manifest).stamp
    assert (stamp.version, stamp.table, stamp.status) == (
        "0.2.0",
        "tool.proj-template",
        "latest",
    )


def test_missing_and_unreadable_stamp(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    assert (
        run(make_repo("none", version=None), template, manifest).stamp.status
        == "missing"
    )
    repo = make_repo("bad-toml", version=None)
    write(repo, "pyproject.toml", "[tool\n")
    assert run(repo, template, manifest).stamp.status == "unreadable"


def test_latest_release_prefers_a_stable_install(manifest: Manifest) -> None:
    assert latest_release(manifest, "0.2.1a0") == "0.2.0"
    assert latest_release(manifest, "0.3.0") == "0.3.0"


def test_fleet_skips_archives_and_unstamped(
    make_repo: MakeRepo, template: Path, manifest: Manifest, tmp_path: Path
) -> None:
    make_repo("alpha")
    make_repo("beta-archive")
    make_repo("gamma", version=None)
    (tmp_path / "repos" / "not-a-repo").mkdir()
    repos = tmp_path / "repos"

    names = [r.name for r in check_fleet(repos, template, manifest, "0.2.0")]
    assert names == ["alpha"]

    everything = check_fleet(
        repos,
        template,
        manifest,
        "0.2.0",
        include_unstamped=True,
        include_archived=True,
    )
    assert [r.name for r in everything] == ["alpha", "beta-archive", "gamma"]


def test_to_dict_carries_current(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    data = run(make_repo("fresh"), template, manifest).to_dict()
    assert data["current"] is True
    assert data["stamp"] == {
        "version": "0.2.0",
        "table": "tool.repotemplates",
        "status": "latest",
        "latest": "0.2.0",
    }


def test_hooks_value_shape_is_compared(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    changed = {"Stop": [*NEW_HOOKS["Stop"], {"matcher": "x"}]}
    files = by_path(run(make_repo("more-hooks", hooks=changed), template, manifest))
    assert files[SETTINGS_HOOKS].status == "one-off"
