"""Tests for PROJECT."""

from typer.testing import CliRunner

from MODULE.cli import app

runner = CliRunner()


def test_hello() -> None:
    result = runner.invoke(app)
    assert result.exit_code == 0
    assert "Hello from PROJECT!" in result.output
