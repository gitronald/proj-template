"""PROJECT CLI."""

import typer

app = typer.Typer(help="PROJECT")


@app.command()
def hello() -> None:
    """Say hello."""
    print("Hello from PROJECT!")
