from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Any, Never

import typer
from pydantic import ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from quality_weaver import __version__
from quality_weaver.catalog import Catalog
from quality_weaver.coverage import validate_ledger
from quality_weaver.io import atomic_write_text
from quality_weaver.models import CoverageLedger
from quality_weaver.testmap import render_testmap
from quality_weaver.workspace import Stage, StateError, Workspace

app = typer.Typer(no_args_is_help=True)
coverage_app = typer.Typer(no_args_is_help=True)
testmap_app = typer.Typer(no_args_is_help=True)
app.add_typer(coverage_app, name="coverage")
app.add_typer(testmap_app, name="testmap")


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


def _artifact_fail(kind: str, error: Exception) -> Never:
    message = str(error).splitlines()[0]
    typer.echo(f"Invalid {kind}: {message}")
    raise typer.Exit(code=1)


def _load_ledger(path: Path) -> CoverageLedger:
    yaml = YAML(typ="safe")
    document: Any = yaml.load(path.read_text(encoding="utf-8"))
    duplicate = _raw_duplicate(document)
    if duplicate is not None:
        raise ValueError(
            f"COVERAGE_DUPLICATE_KEY {duplicate}: Coverage logical key is duplicated"
        )
    return CoverageLedger.model_validate(document)


def _catalog(path: Path) -> Catalog:
    return Catalog.load(path)


def _raw_duplicate(document: Any) -> str | None:
    if not isinstance(document, Mapping) or not isinstance(document.get("items"), list):
        return None
    seen: set[tuple[Any, Any, Any, Any]] = set()
    for item in document["items"]:
        if not isinstance(item, Mapping):
            continue
        key = (
            item.get("requirement_id"),
            item.get("target_id"),
            item.get("viewpoint_id"),
            item.get("condition"),
        )
        if not all(isinstance(value, str) for value in key):
            continue
        if key in seen:
            artifact_id = item.get("id")
            return str(artifact_id) if artifact_id is not None else "coverage-ledger"
        seen.add(key)
    return None


def _target_ownership(
    requirement_ids: list[str], target_specs: list[str]
) -> dict[str, set[str]]:
    ownership: dict[str, set[str]] = {
        requirement_id: set() for requirement_id in requirement_ids
    }
    for spec in target_specs:
        requirement_id, separator, target_id = spec.partition("=")
        if not separator or not requirement_id or not target_id:
            raise ValueError(f"target must use REQUIREMENT_ID=TARGET_ID: {spec}")
        if requirement_id not in ownership:
            raise ValueError(f"target references undeclared requirement: {requirement_id}")
        ownership[requirement_id].add(target_id)
    return ownership


@coverage_app.command("validate")
def coverage_validate(
    ledger_path: Annotated[Path, typer.Argument(metavar="LEDGER")],
    catalog_path: Annotated[Path, typer.Option("--catalog")],
    requirement_ids: Annotated[list[str], typer.Option("--requirement-id")],
    target_specs: Annotated[list[str], typer.Option("--target")],
) -> None:
    """Validate a Coverage Ledger with explicit lookup inputs."""
    try:
        ledger = _load_ledger(ledger_path)
        catalog = _catalog(catalog_path)
        target_ownership = _target_ownership(requirement_ids, target_specs)
    except (OSError, ValueError, ValidationError, YAMLError) as error:
        _artifact_fail("coverage ledger", error)
    findings = validate_ledger(
        ledger,
        known_requirement_ids=set(requirement_ids),
        known_target_ids=target_ownership,
        catalog=catalog,
    )
    for finding in findings:
        typer.echo(f"{finding.code} {finding.artifact_id}: {finding.message}")
    if any(finding.blocking for finding in findings):
        raise typer.Exit(code=1)
    typer.echo("Coverage ledger is valid")


@testmap_app.command("render")
def testmap_render(
    ledger_path: Annotated[Path, typer.Argument(metavar="LEDGER")],
    output_path: Annotated[Path, typer.Option("--out")],
    catalog_path: Annotated[Path, typer.Option("--catalog")],
    requirement_ids: Annotated[list[str], typer.Option("--requirement-id")],
    target_specs: Annotated[list[str], typer.Option("--target")],
) -> None:
    """Render the deterministic Test Map projection."""
    try:
        ledger = _load_ledger(ledger_path)
        catalog = _catalog(catalog_path)
        target_ownership = _target_ownership(requirement_ids, target_specs)
        markdown = render_testmap(
            ledger,
            catalog,
            known_requirement_ids=set(requirement_ids),
            known_target_ids=target_ownership,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(output_path, markdown)
    except (OSError, ValueError, ValidationError, YAMLError) as error:
        _artifact_fail("coverage ledger", error)
    typer.echo(f"Rendered {output_path}")


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
    typer.echo(f"Next: {workspace.next_action(state)}")


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


@app.command()
def regenerate(
    stage: Stage,
    project_path: Annotated[Path, typer.Argument(metavar="[PATH]")] = Path("."),
) -> None:
    """Reset a stale gate to draft before regenerating its artifact."""
    workspace = _workspace(project_path)
    try:
        workspace.regenerate(stage)
    except StateError as error:
        _fail(error)
    typer.echo(f"Ready to regenerate {stage.value}")
