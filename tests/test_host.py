"""The packaged skills: their layout, the commands they name, and installs."""

from __future__ import annotations

from pathlib import Path

import pytest
from pkgskills.testing import (
    assert_prompt_commands,
    assert_spec_conformant,
    sandbox,
)
from typer.testing import CliRunner

from repotemplates.cli import app
from repotemplates.host import HOST

SKILLS = ("install-template", "install-renovatabot")


def test_spec_conformant() -> None:
    assert_spec_conformant(HOST)


def test_prompt_commands_exist() -> None:
    # Every `{cli} <command>` a body names is a command the CLI has
    assert_prompt_commands(HOST, app)


@pytest.mark.parametrize("name", SKILLS)
def test_skill_prints_body(name: str) -> None:
    result = CliRunner().invoke(app, ["skill", name])
    assert result.exit_code == 0
    assert result.output.startswith("# ")
    assert "{cli}" not in result.output


def test_bodies_name_no_checkout_paths() -> None:
    # A printed body has no checkout around it, so `scripts/...` resolves nowhere
    for name in SKILLS:
        out = CliRunner().invoke(app, ["skill", name]).output
        assert "`scripts/" not in out
        assert "docs/guides/" not in out or "github.com" in out


def test_global_install_writes_stubs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    box = sandbox(tmp_path, monkeypatch)
    runner = CliRunner()
    assert runner.invoke(app, ["install"]).exit_code == 0
    for name in SKILLS:
        stub = box.home / ".claude/skills" / name / "SKILL.md"
        text = stub.read_text()
        assert f"repotemplates skill {name}" in text
        assert 'pkgskills-mode: "global"' in text
        assert (box.home / ".agents/skills" / name / "SKILL.md").is_file()
    assert runner.invoke(app, ["install", "--check"]).exit_code == 0


def test_local_install_uses_uv_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    box = sandbox(tmp_path, monkeypatch)
    assert CliRunner().invoke(app, ["install", "--local"]).exit_code == 0
    stub = box.repo / ".claude/skills/install-template/SKILL.md"
    assert "uv run repotemplates skill install-template" in stub.read_text()
