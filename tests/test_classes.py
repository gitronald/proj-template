"""The comparison rules for pinned, config, and ignore files, and omissions."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from conftest import git_init, write

from repotemplates.check import check_repo, omitted
from repotemplates.classes import (
    attribute_gaps,
    compare_pins,
    ignore_gaps,
    mask,
    merge_pinned,
    pins,
)
from repotemplates.manifest import DirSource, Manifest, fingerprint

MakeRepo = Callable[..., Path]

WORKFLOW = """\
jobs:
  test:
    strategy:
      matrix:
        python-version: ["3.11", "3.12", "3.13", "3.14"]
    steps:
      - uses: actions/checkout@aaaa  # v7.0.1
      - uses: astral-sh/setup-uv@bbbb  # v10.3.0
      - run: uv run pytest
"""
PRECOMMIT = """\
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.17.1
    hooks:
      - id: ruff-format
"""


def bump(text: str, old: str, new: str) -> str:
    assert old in text
    return text.replace(old, new)


# --- pinned -----------------------------------------------------------------


def test_mask_hides_pins_and_matrix() -> None:
    masked = mask(WORKFLOW)
    assert "aaaa" not in masked and "v7.0.1" not in masked
    assert "actions/checkout@<pin>" in masked
    assert "python-version: <matrix>" in masked
    assert mask(bump(WORKFLOW, '"3.11", ', "")) == masked
    assert "rev: <pin>" in mask(PRECOMMIT)


def test_mask_keeps_other_changes() -> None:
    assert mask(WORKFLOW + "      - run: extra\n") != mask(WORKFLOW)
    # A different action is a different file, not a pin bump
    assert mask(bump(WORKFLOW, "astral-sh/setup-uv", "other/setup")) != mask(WORKFLOW)


def test_pins_names_and_versions() -> None:
    assert [(p.name, p.version) for p in pins(WORKFLOW)] == [
        ("actions/checkout", "v7.0.1"),
        ("astral-sh/setup-uv", "v10.3.0"),
    ]
    assert [(p.name, p.version) for p in pins(PRECOMMIT)] == [
        ("https://github.com/astral-sh/ruff-pre-commit", "v0.17.1")
    ]


@pytest.mark.parametrize(
    ("repo_text", "expected"),
    [
        (WORKFLOW, "same"),
        (bump(WORKFLOW, "bbbb  # v10.3.0", "cccc  # v10.3.3"), "ahead"),
        (bump(WORKFLOW, "aaaa  # v7.0.1", "dddd  # v6.0.0"), "behind"),
        (
            bump(
                bump(WORKFLOW, "aaaa  # v7.0.1", "dddd  # v6.0.0"),
                "bbbb  # v10.3.0",
                "cccc  # v10.3.3",
            ),
            "mixed",
        ),
        (bump(WORKFLOW, "aaaa  # v7.0.1", "eeee"), "differs"),
    ],
)
def test_compare_pins(repo_text: str, expected: str) -> None:
    assert compare_pins(repo_text, WORKFLOW) == expected


def test_compare_pins_rev() -> None:
    assert compare_pins(bump(PRECOMMIT, "v0.17.1", "v0.17.3"), PRECOMMIT) == "ahead"
    assert compare_pins(bump(PRECOMMIT, "v0.17.1", "v0.9.0"), PRECOMMIT) == "behind"


def test_merge_keeps_newer_pins_and_matrix() -> None:
    old = bump(WORKFLOW, "aaaa  # v7.0.1", "dddd  # v6.0.0")
    old = bump(old, "bbbb  # v10.3.0", "cccc  # v10.3.3")
    old = bump(old, '"3.11", ', "")
    old = bump(old, "      - run: uv run pytest\n", "")  # older structure
    merged = merge_pinned(WORKFLOW, old)
    assert "actions/checkout@aaaa  # v7.0.1" in merged  # raised to the template's
    assert "astral-sh/setup-uv@cccc  # v10.3.3" in merged  # repo's newer pin kept
    assert 'python-version: ["3.12", "3.13", "3.14"]' in merged
    assert "uv run pytest" in merged  # the template's structure
    assert mask(merged) == mask(WORKFLOW)


# --- ignore files ------------------------------------------------------------

TEMPLATE_IGNORE = ".claude/\n.venv/\n*.egg-info/\n.env\n.env.*\n!.env.example\n"


def ignore_repo(tmp_path: Path, text: str) -> Path:
    repo = git_init(tmp_path / "repo")
    write(repo, ".gitignore", text)
    return repo


@pytest.mark.parametrize("spelling", [".claude", ".claude/", ".claude/*", "/.claude/"])
def test_ignore_spellings_all_hold(tmp_path: Path, spelling: str) -> None:
    text = TEMPLATE_IGNORE.replace(".claude/\n", f"{spelling}\n")
    repo = ignore_repo(tmp_path, text + "data/\n")  # a local addition is fine
    assert ignore_gaps(repo, TEMPLATE_IGNORE) == ([], [])


def test_ignore_gaps_and_negation(tmp_path: Path) -> None:
    repo = ignore_repo(tmp_path, ".claude/\n.venv/\n.env\n.env.*\n")
    gaps, waived = ignore_gaps(repo, TEMPLATE_IGNORE)
    assert gaps == ["*.egg-info/", "!.env.example"]
    assert waived == []


def test_ignore_rule_waived_when_repo_tracks_under_it(tmp_path: Path) -> None:
    repo = ignore_repo(tmp_path, TEMPLATE_IGNORE.replace(".claude/\n", ""))
    write(repo, ".claude/settings.json", "{}")
    subprocess.run(["git", "add", ".claude/settings.json"], cwd=repo, check=True)
    assert ignore_gaps(repo, TEMPLATE_IGNORE) == ([], [".claude/"])


def test_attribute_gaps(tmp_path: Path) -> None:
    repo = git_init(tmp_path / "repo")
    template = ".planners/README.md merge=union\n"
    assert attribute_gaps(repo, template) == [template.strip()]
    write(repo, ".gitattributes", "*.png binary\n.planners/README.md  merge=union\n")
    assert attribute_gaps(repo, template) == []


# --- omissions and check_repo --------------------------------------------------


def test_updaters_exclude_each_other(tmp_path: Path) -> None:
    write(tmp_path / "dep", ".github/dependabot.yml", "")
    assert omitted(tmp_path / "dep", ()) == {
        ".github/renovate.json",
        ".github/workflows/renovate.yml",
    }
    write(tmp_path / "ren", ".github/renovate.json", "{}")
    assert omitted(tmp_path / "ren", ("x.yml",)) == {".github/dependabot.yml", "x.yml"}


@pytest.fixture
def full_template(template: Path) -> Path:
    write(template, ".github/workflows/test.yml", WORKFLOW)
    write(template, ".github/workflows/publish.yml", WORKFLOW)
    write(template, ".github/dependabot.yml", "version: 2\n")
    write(template, ".gitignore", TEMPLATE_IGNORE)
    return template


def statuses(
    repo: Path, template: Path, manifest: Manifest
) -> dict[str, tuple[str, str | None]]:
    report = check_repo(repo, template, manifest, "0.2.0")
    return {f.path: (f.status, f.pins) for f in report.files}


def test_check_pinned_config_ignore(
    make_repo: MakeRepo, full_template: Path, manifest: Manifest
) -> None:
    repo = make_repo("r")
    write(repo, ".github/workflows/test.yml", bump(WORKFLOW, "v10.3.0", "v10.4.0"))
    write(repo, ".github/dependabot.yml", "version: 2\n")
    write(repo, ".gitignore", TEMPLATE_IGNORE)
    got = statuses(repo, full_template, manifest)
    assert got[".github/workflows/test.yml"] == ("current", "ahead")
    assert got[".github/workflows/publish.yml"] == ("missing", None)
    assert got[".github/dependabot.yml"] == ("current", None)
    assert got[".gitignore"] == ("current", None)
    report = check_repo(repo, full_template, manifest, "0.2.0")
    assert not report.current  # publish.yml is missing

    write(
        repo,
        "pyproject.toml",
        '[tool.repotemplates]\nversion = "0.2.0"\n'
        'omit = [".github/workflows/publish.yml"]\n',
    )
    got = statuses(repo, full_template, manifest)
    assert got[".github/workflows/publish.yml"] == ("omitted", None)
    assert check_repo(repo, full_template, manifest, "0.2.0").current


def test_pins_behind_is_not_current(
    make_repo: MakeRepo, full_template: Path, manifest: Manifest
) -> None:
    repo = make_repo("r")
    write(repo, ".github/workflows/test.yml", bump(WORKFLOW, "v10.3.0", "v9.0.0"))
    report = check_repo(repo, full_template, manifest, "0.2.0")
    test_yml = next(f for f in report.files if f.path == ".github/workflows/test.yml")
    assert (test_yml.status, test_yml.pins) == ("current", "behind")
    assert not test_yml.current


def test_pinned_matches_an_earlier_release(
    make_repo: MakeRepo, full_template: Path, tmp_path: Path
) -> None:
    old = tmp_path / "old"
    write(
        old,
        ".github/workflows/test.yml",
        WORKFLOW.replace("run: uv run pytest", "run: old"),
    )
    prints = fingerprint(DirSource(old))
    manifest = Manifest(["0.1.0"], {k: {"0.1.0": v} for k, v in prints.items()})
    repo = make_repo("r")
    write(
        repo,
        ".github/workflows/test.yml",
        (old / ".github/workflows/test.yml").read_text(),
    )
    got = statuses(repo, full_template, manifest)
    assert got[".github/workflows/test.yml"] == ("matches", "same")
