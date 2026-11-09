from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from repotemplates import paths
from repotemplates.cli import main
from repotemplates.manifest import SETTINGS_HOOKS

MakeRepo = Callable[..., Path]


@pytest.fixture
def real_repo(tmp_path: Path) -> Path:
    """A repo carrying the shipped template's Claude files and the latest stamp."""
    repo = tmp_path / "scaffolded"
    shutil.copytree(paths.template_root() / ".claude", repo / ".claude")
    (repo / "pyproject.toml").write_text('[tool.repotemplates]\nversion = "0.12.0"\n')
    return repo


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["version"]) == 0
    assert capsys.readouterr().out.strip() == paths.version()


def test_shipped_template_checks_current(
    real_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["check", str(real_repo), "--json"])
    report = json.loads(capsys.readouterr().out)
    statuses = {f["path"]: f["status"] for f in report["files"]}
    assert statuses[SETTINGS_HOOKS] == "current"
    assert set(statuses.values()) == {"current"}
    # The stamp is current only when 0.12.0 is the newest stable release
    assert code == (0 if report["stamp"]["status"] == "latest" else 1)


def test_drift_exits_1(real_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (real_repo / ".claude/hooks/lint-typecheck.sh").write_text("echo edited\n")
    assert main(["check", str(real_repo)]) == 1
    out = capsys.readouterr().out
    assert "one-off" in out
    assert out.startswith("repo: scaffolded")


def test_markdown(real_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["check", str(real_repo), "--markdown"])
    out = capsys.readouterr().out
    assert "| file | status | git |" in out
    assert "- stamp: 0.12.0" in out


def test_fleet_json_is_an_array(
    real_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (real_repo / ".git").mkdir()
    main(["check", "--repos-dir", str(real_repo.parent), "--json"])
    reports = json.loads(capsys.readouterr().out)
    assert [r["name"] for r in reports] == ["scaffolded"]


def test_fleet_table(real_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (real_repo / ".git").mkdir()
    main(["check", "--repos-dir", str(real_repo.parent)])
    out = capsys.readouterr().out
    assert out.splitlines()[0].split()[:3] == ["repo", "stamp", "stamp"]
    assert "scaffolded" in out


@pytest.mark.parametrize(
    "argv",
    [
        ["check", ".", "--repos-dir", "."],
        ["check", "--all"],
        ["check", "--json", "--markdown"],
        ["check", "does-not-exist"],
        ["nonsense"],
        [],
    ],
)
def test_usage_errors_exit_2(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert exc.value.code == 2
