"""PACKAGE CLI."""

import typer

app = typer.Typer(help="PACKAGE")


@app.command()
def hello() -> None:
    """Say hello."""
    print("Hello from PACKAGE!")
