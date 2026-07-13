import typer

from quality_weaver import __version__

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """QualityWeaver command-line interface."""


@app.command()
def version() -> None:
    """Print the installed QualityWeaver version."""
    typer.echo(f"quality-weaver {__version__}")
