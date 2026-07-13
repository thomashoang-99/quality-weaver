from pathlib import Path
from typing import Annotated, Never

import typer

from quality_weaver import __version__
from quality_weaver.workspace import Stage, StateError, Workspace

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """QualityWeaver command-line interface."""


@app.command()
def version() -> None:
    """Print the installed QualityWeaver version."""
    typer.echo(f"quality-weaver {__version__}")


def _workspace(project_path: Path) -> Workspace:
    return Workspace(project_path)


def _fail(error: StateError) -> Never:
    typer.echo(f"State error: {error}")
    raise typer.Exit(code=1)


@app.command("init")
def init_workspace(
    project_path: Annotated[Path, typer.Argument(metavar="[PATH]")] = Path("."),
) -> None:
    """Initialize a QualityWeaver workspace."""
    try:
        workspace = Workspace.init(project_path)
    except StateError as error:
        _fail(error)
    typer.echo(f"Initialized {workspace.path}")


@app.command()
def status(
    project_path: Annotated[Path, typer.Argument(metavar="[PATH]")] = Path("."),
) -> None:
    """Show approval gates and the next legal action."""
    workspace = _workspace(project_path)
    try:
        state = workspace.load_state()
    except StateError as error:
        _fail(error)

    typer.echo("Stage         Status")
    for stage in Stage:
        typer.echo(f"{stage.value:<13} {getattr(state, stage.value).value}")
    typer.echo(f"Next: {workspace.next_action()}")


@app.command()
def approve(
    stage: Stage,
    project_path: Annotated[Path, typer.Argument(metavar="[PATH]")] = Path("."),
) -> None:
    """Approve a workspace gate."""
    workspace = _workspace(project_path)
    try:
        workspace.approve(stage)
    except StateError as error:
        _fail(error)
    typer.echo(f"Approved {stage.value}")
