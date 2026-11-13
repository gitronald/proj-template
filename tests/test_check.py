from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest
from conftest import (
    HOOK,
    NEW_HOOKS,
    OLD_HOOK,
    OLD_HOOKS,
    RETIRED,
    RETIRED_HOOK,
    add_worktree,
    write,
)
from conftest import settings as settings_text

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
        "omit": (),
        "keep": {},
    }


def test_hooks_value_shape_is_compared(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    changed = {"Stop": [*NEW_HOOKS["Stop"], {"matcher": "x"}]}
    files = by_path(run(make_repo("more-hooks", hooks=changed), template, manifest))
    assert files[SETTINGS_HOOKS].status == "one-off"


def test_malformed_stamp_table(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    cases = {
        "not-a-table": '[tool]\nrepotemplates = "0.2.0"\n',
        "omit-not-a-list": '[tool.repotemplates]\nomit = "a.yml"\n',
        "keep-a-list": '[tool.repotemplates]\nversion = "0.2.0"\nkeep = ["a.yml"]\n',
        "keep-no-release": '[tool.repotemplates]\nkeep = {"a.yml" = 1}\n',
        "keep-not-a-version": '[tool.repotemplates]\nkeep = {"a.yml" = "soon"}\n',
        "number-version": "[tool.proj-template]\nversion = 2\n",
        "tool-not-a-table": 'tool = "x"\n',
    }
    for name, text in cases.items():
        repo = make_repo(name, version=None)
        write(repo, "pyproject.toml", text)
        assert run(repo, template, manifest).stamp.status == "unreadable", name


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads a mode 000 file")
def test_unreadable_hook_file(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    repo = make_repo("locked")
    (repo / HOOK).chmod(0)
    try:
        assert by_path(run(repo, template, manifest))[HOOK].status == "unreadable"
        reports = check_fleet(repo.parent, template, manifest, "0.2.0")
        assert [r.name for r in reports] == ["locked"]
    finally:
        (repo / HOOK).chmod(0o644)


def test_git_not_on_path(
    make_repo: MakeRepo,
    template: Path,
    manifest: Manifest,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo = make_repo("gitless")
    monkeypatch.setenv("PATH", str(tmp_path / "empty-bin"))
    report = run(repo, template, manifest)
    assert report.settings[".claude/settings.json"] == "no git"
    assert {f.git for f in report.files} == {"no git"}


def test_table_without_version_is_not_stamped_yet(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    # Written by hand before the first stamp, to hold omit: missing, not
    # unreadable, and the omit still counts
    repo = make_repo("first", version=None, hook=None)
    write(repo, "pyproject.toml", f'[tool.repotemplates]\nomit = ["{HOOK}"]\n')
    report = run(repo, template, manifest)
    assert (report.stamp.status, report.stamp.table, report.stamp.omit) == (
        "missing",
        "tool.repotemplates",
        (HOOK,),
    )
    assert by_path(report)[HOOK].status == "omitted"
    repo = make_repo("other-key", version=None)
    write(repo, "pyproject.toml", "[tool.repotemplates]\nother = 1\n")
    assert run(repo, template, manifest).stamp.status == "missing"


def test_worktree_reads_ignored_files_from_the_main_checkout(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    repo = make_repo("ignores", ignore=".claude/\n")
    tree = add_worktree(repo, ".gitignore", "pyproject.toml")
    assert not (tree / HOOK).exists()
    report = run(tree, template, manifest)
    main = str(repo.resolve())
    assert [(f.path, f.status, f.git, f.source) for f in report.files] == [
        (HOOK, "current", "ignored", main),
        (SETTINGS_HOOKS, "current", "ignored", main),
    ]
    assert report.settings[".claude/settings.json"] == "ignored"
    assert report.current
    # The main checkout itself reads its own files
    assert {f.source for f in run(repo, template, manifest).files} == {None}


def test_worktree_reads_a_behind_copy_from_the_main_checkout(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    repo = make_repo("ignores-old", hook=OLD_HOOK, ignore=".claude/\n")
    tree = add_worktree(repo, ".gitignore", "pyproject.toml")
    hook = by_path(run(tree, template, manifest))[HOOK]
    assert (hook.status, hook.release, hook.source) == (
        "matches",
        "0.1.0",
        str(repo.resolve()),
    )


def test_worktree_missing_file_not_ignored_stays_missing(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    # Untracked but not ignored: lost from the branch, not kept out of it
    tree = add_worktree(make_repo("untracked"), "pyproject.toml")
    files = by_path(run(tree, template, manifest))
    assert (files[HOOK].status, files[HOOK].source) == ("missing", None)


def kept_repo(make_repo: MakeRepo, name: str, keep: str) -> Path:
    repo = make_repo(name, version=None, hook=b"echo mine\n")
    write(repo, "pyproject.toml", f'[tool.repotemplates]\nversion = "0.2.0"\n{keep}')
    return repo


def test_kept_file_reads_current(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    repo = kept_repo(make_repo, "kept", f'keep = {{"{HOOK}" = "0.2.0"}}\n')
    report = run(repo, template, manifest)
    hook = by_path(report)[HOOK]
    assert (hook.status, hook.release, hook.detail) == ("kept", "0.2.0", ())
    assert report.stamp.keep == {HOOK: "0.2.0"}
    assert report.current


def test_kept_file_behind_once_the_template_moves(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    # The template's hook changed between 0.1.0 and 0.2.0
    repo = kept_repo(make_repo, "kept-old", f'keep = {{"{HOOK}" = "0.1.0"}}\n')
    report = run(repo, template, manifest)
    hook = by_path(report)[HOOK]
    assert (hook.status, hook.release) == ("kept-behind", "0.1.0")
    assert hook.detail == ("the template's copy changed after v0.1.0",)
    assert not report.current
    # Unchanged since that release: still kept
    files = {**manifest.files, HOOK: {**manifest.files[HOOK]}}
    files[HOOK]["0.1.0"] = files[HOOK]["0.2.0"]
    same = Manifest(manifest.releases, files)
    assert by_path(run(repo, template, same))[HOOK].status == "kept"


def test_kept_release_unknown_or_settings_by_path(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    repo = kept_repo(
        make_repo,
        "kept-odd",
        f'keep = {{"{HOOK}" = "0.0.9", ".claude/settings.json" = "0.2.0"}}\n',
    )
    write(repo, ".claude/settings.json", settings_text({"Stop": []}))
    files = by_path(run(repo, template, manifest))
    assert files[HOOK].status == "kept-behind"
    assert files[HOOK].detail == ("v0.0.9 is not a release this install knows",)
    # The settings file's path names its hooks block
    assert files[SETTINGS_HOOKS].status == "kept"


def test_kept_entry_does_not_hide_an_earlier_release(
    make_repo: MakeRepo, template: Path, manifest: Manifest
) -> None:
    repo = kept_repo(make_repo, "kept-match", f'keep = {{"{HOOK}" = "0.2.0"}}\n')
    write(repo, HOOK, OLD_HOOK)
    assert by_path(run(repo, template, manifest))[HOOK].status == "matches"
