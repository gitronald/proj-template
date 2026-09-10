"""PROJECT__NAME CLI."""

import typer

app = typer.Typer(help="PROJECT__NAME")


@app.command()
def hello() -> None:
    """Say hello."""
    print("Hello from PROJECT__NAME!")
