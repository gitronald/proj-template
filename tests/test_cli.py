from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from repotemplates import paths
from repotemplates.cli import app
from repotemplates.manifest import SETTINGS_HOOKS

MakeRepo = Callable[..., Path]


def run(*argv: str) -> tuple[int, str]:
    result = CliRunner().invoke(app, list(argv))
    return result.exit_code, result.output


@pytest.fixture
def real_repo(tmp_path: Path) -> Path:
    """A repo carrying the shipped template's Claude files and the latest stamp."""
    repo = tmp_path / "scaffolded"
    shutil.copytree(paths.template_root() / ".claude", repo / ".claude")
    (repo / "pyproject.toml").write_text('[tool.repotemplates]\nversion = "0.12.0"\n')
    return repo


def test_version() -> None:
    assert run("version") == (0, f"{paths.version()}\n")
    assert run("--version") == (0, f"repotemplates {paths.version()}\n")


@pytest.mark.parametrize(
    ("what", "expected"),
    [("template", paths.template_root()), ("scripts", paths.scripts_root())],
)
def test_path(what: str, expected: Path) -> None:
    assert run("path", what) == (0, f"{expected}\n")
    assert (paths.scripts_root() / "init.sh").is_file()


def test_shipped_template_checks_current(real_repo: Path) -> None:
    code, out = run("check", str(real_repo), "--json")
    report = json.loads(out)
    statuses = {f["path"]: f["status"] for f in report["files"]}
    assert statuses[SETTINGS_HOOKS] == "current"
    assert set(statuses.values()) == {"current"}
    # The stamp is current only when 0.12.0 is the newest stable release
    assert code == (0 if report["stamp"]["status"] == "latest" else 1)


def test_drift_exits_1(real_repo: Path) -> None:
    (real_repo / ".claude/hooks/lint-typecheck.sh").write_text("echo edited\n")
    code, out = run("check", str(real_repo))
    assert code == 1
    assert "one-off" in out
    assert out.startswith("repo: scaffolded")


def test_markdown(real_repo: Path) -> None:
    _, out = run("check", str(real_repo), "--markdown")
    assert "| file | status | git |" in out
    assert "- stamp: 0.12.0" in out


def test_fleet_json_is_an_array(real_repo: Path) -> None:
    (real_repo / ".git").mkdir()
    _, out = run("check", "--repos-dir", str(real_repo.parent), "--json")
    reports = json.loads(out)
    assert [r["name"] for r in reports] == ["scaffolded"]


def test_fleet_table(real_repo: Path) -> None:
    (real_repo / ".git").mkdir()
    _, out = run("check", "--repos-dir", str(real_repo.parent))
    assert out.splitlines()[0].split()[:3] == ["repo", "stamp", "stamp"]
    assert "scaffolded" in out


@pytest.mark.parametrize(
    "argv",
    [
        ["check", ".", "--repos-dir", "."],
        ["check", "--all"],
        ["check", "--json", "--markdown"],
        ["check", "does-not-exist"],
        ["path", "nonsense"],
        ["nonsense"],
        [],
    ],
)
def test_usage_errors_exit_2(argv: list[str]) -> None:
    assert run(*argv)[0] == 2


def test_empty_fleet_exits_1(tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()
    code, out = run("check", "--repos-dir", str(tmp_path / "empty"))
    assert code == 1
    assert "no repos to check" in out
