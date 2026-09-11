"""Tests for PROJECT__NAME."""

from typer.testing import CliRunner

from MODULE__NAME.cli import app

runner = CliRunner()


def test_hello() -> None:
    result = runner.invoke(app)
    assert result.exit_code == 0
    assert "Hello from PROJECT__NAME!" in result.output
