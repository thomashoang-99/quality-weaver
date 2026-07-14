from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Any, Never

import typer
from pydantic import TypeAdapter, ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from quality_weaver import __version__
from quality_weaver.catalog import Catalog
from quality_weaver.coverage import CoverageFinding, validate_ledger
from quality_weaver.exporters import ExportError, export_excel, export_markdown
from quality_weaver.io import atomic_write_text
from quality_weaver.models import (
    ApprovalStatus,
    CoverageItem,
    CoverageLedger,
    RequirementDocument,
    TestCaseDocument,
    TestOutline,
)
from quality_weaver.profiles import ExportFormat, Profile, ProfileError
from quality_weaver.testcases import (
    parse_testcases_markdown,
    render_testcases_markdown,
    validate_outline,
    validate_testcases,
)
from quality_weaver.testmap import render_testmap
from quality_weaver.workspace import Stage, StateError, Workspace

app = typer.Typer(no_args_is_help=True)
requirements_app = typer.Typer(no_args_is_help=True)
coverage_app = typer.Typer(no_args_is_help=True)
testmap_app = typer.Typer(no_args_is_help=True)
outline_app = typer.Typer(no_args_is_help=True)
testcases_app = typer.Typer(no_args_is_help=True)
app.add_typer(requirements_app, name="requirements")
app.add_typer(coverage_app, name="coverage")
app.add_typer(testmap_app, name="testmap")
app.add_typer(outline_app, name="outline")
app.add_typer(testcases_app, name="testcases")
_COVERAGE_ITEMS = TypeAdapter(list[CoverageItem])


class _DuplicateCoverageError(ValueError):
    def __init__(self, findings: list[CoverageFinding]) -> None:
        self.findings = tuple(findings)
        super().__init__("coverage ledger contains duplicate coverage")


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


def _export_fail(error: ExportError) -> Never:
    for finding in error.findings:
        typer.echo(f"{finding.code} {finding.artifact_id}: {finding.message}")
    raise typer.Exit(code=1)


def _load_ledger(path: Path) -> CoverageLedger:
    yaml = YAML(typ="safe")
    document: Any = yaml.load(path.read_text(encoding="utf-8"))
    items = _validated_raw_items(document)
    duplicate_findings = _duplicate_findings(items)
    if duplicate_findings:
        raise _DuplicateCoverageError(duplicate_findings)
    return CoverageLedger.model_validate(document)


def _load_outline(path: Path) -> TestOutline:
    yaml = YAML(typ="safe")
    return TestOutline.model_validate(yaml.load(path.read_text(encoding="utf-8")))


def _load_requirement(path: Path) -> RequirementDocument:
    yaml = YAML(typ="safe")
    return RequirementDocument.model_validate(yaml.load(path.read_text(encoding="utf-8")))


def _load_testcases(path: Path) -> TestCaseDocument:
    if path.suffix.lower() == ".md":
        return parse_testcases_markdown(path.read_text(encoding="utf-8"))
    yaml = YAML(typ="safe")
    return TestCaseDocument.model_validate(yaml.load(path.read_text(encoding="utf-8")))


def _catalog(path: Path) -> Catalog:
    return Catalog.load(path)


def _validated_raw_items(document: Any) -> list[CoverageItem]:
    if not isinstance(document, Mapping) or not isinstance(document.get("items"), list):
        return []
    return _COVERAGE_ITEMS.validate_python(document["items"])


def _duplicate_findings(items: list[CoverageItem]) -> list[CoverageFinding]:
    ids_by_key: dict[tuple[str, str, str, str], list[str]] = {}
    for item in items:
        ids_by_key.setdefault(item.logical_key, []).append(item.id)
    findings = [
        ("COVERAGE_DUPLICATE_KEY", min(coverage_ids), "Coverage logical key is duplicated")
        for coverage_ids in ids_by_key.values()
        if len(coverage_ids) > 1
    ]
    findings.extend(
        ("COVERAGE_DUPLICATE_ID", coverage_id, "Coverage ID is duplicated")
        for coverage_id, count in Counter(item.id for item in items).items()
        if count > 1
    )
    return sorted(
        (
            CoverageFinding(code=code, artifact_id=artifact_id, message=message)
            for code, artifact_id, message in findings
        ),
        key=lambda finding: (finding.code, finding.artifact_id, finding.message),
    )


def _ensure_safe_output(ledger_path: Path, catalog_path: Path, output_path: Path) -> None:
    resolved_output = output_path.resolve()
    resolved_ledger = ledger_path.resolve()
    protected_inputs = _catalog_input_paths(catalog_path)
    if resolved_output == resolved_ledger or resolved_output in protected_inputs:
        raise ValueError("output path collides with a protected input")


def _catalog_input_paths(catalog_path: Path) -> set[Path]:
    resolved_catalog = catalog_path.resolve()
    metadata_path = (resolved_catalog / "catalog.yaml").resolve()
    yaml = YAML(typ="safe")
    metadata: Any = yaml.load(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(metadata, Mapping) or not isinstance(metadata.get("groups"), list):
        raise ValueError("catalog.yaml requires list groups")
    protected = {metadata_path}
    for group in metadata["groups"]:
        if not isinstance(group, Mapping) or not isinstance(group.get("file"), str):
            raise ValueError("catalog group requires string file")
        source = (resolved_catalog / group["file"]).resolve()
        if not source.is_relative_to(resolved_catalog):
            raise ValueError(f"catalog file escapes root: {group['file']}")
        protected.add(source)
    return protected


def _duplicates_fail(error: _DuplicateCoverageError) -> Never:
    for finding in error.findings:
        typer.echo(f"{finding.code} {finding.artifact_id}: {finding.message}")
    raise typer.Exit(code=1)


def _findings_result(findings: list[CoverageFinding], success: str) -> None:
    for finding in findings:
        typer.echo(f"{finding.code} {finding.artifact_id}: {finding.message}")
    if any(finding.blocking for finding in findings):
        raise typer.Exit(code=1)
    typer.echo(success)


def _ensure_distinct_output(output_path: Path, *input_paths: Path) -> None:
    resolved_output = output_path.resolve()
    if resolved_output in {path.resolve() for path in input_paths}:
        raise ValueError("output path collides with an input")


def _target_ownership(requirement_ids: list[str], target_specs: list[str]) -> dict[str, set[str]]:
    ownership: dict[str, set[str]] = {requirement_id: set() for requirement_id in requirement_ids}
    for spec in target_specs:
        requirement_id, separator, target_id = spec.partition("=")
        if not separator or not requirement_id or not target_id:
            raise ValueError(f"target must use REQUIREMENT_ID=TARGET_ID: {spec}")
        if requirement_id not in ownership:
            raise ValueError(f"target references undeclared requirement: {requirement_id}")
        ownership[requirement_id].add(target_id)
    return ownership


@requirements_app.command("validate")
def requirements_validate(
    requirement_path: Annotated[Path, typer.Argument(metavar="PATH")],
) -> None:
    """Validate a normalized requirement document."""
    try:
        _load_requirement(requirement_path)
    except (OSError, ValueError, ValidationError, YAMLError) as error:
        _artifact_fail("requirement document", error)
    typer.echo("Requirement document is valid")


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
    except _DuplicateCoverageError as error:
        _duplicates_fail(error)
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
        _ensure_safe_output(ledger_path, catalog_path, output_path)
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
    except _DuplicateCoverageError as error:
        _duplicates_fail(error)
    except (OSError, ValueError, ValidationError, YAMLError) as error:
        _artifact_fail("coverage ledger", error)
    typer.echo(f"Rendered {output_path}")


@outline_app.command("validate")
def outline_validate(
    ledger_path: Annotated[Path, typer.Argument(metavar="LEDGER")],
    outline_path: Annotated[Path, typer.Argument(metavar="OUTLINE")],
) -> None:
    """Validate exact coverage consumption by a test outline."""
    try:
        ledger = _load_ledger(ledger_path)
        outline = _load_outline(outline_path)
    except _DuplicateCoverageError as error:
        _duplicates_fail(error)
    except (OSError, ValueError, ValidationError, YAMLError) as error:
        _artifact_fail("outline input", error)
    _findings_result(validate_outline(ledger, outline), "Outline is valid")


@testcases_app.command("validate")
def testcases_validate(
    ledger_path: Annotated[Path, typer.Argument(metavar="LEDGER")],
    outline_path: Annotated[Path, typer.Argument(metavar="OUTLINE")],
    cases_path: Annotated[Path, typer.Argument(metavar="CASES")],
) -> None:
    """Validate detailed test cases against explicit ledger and outline inputs."""
    try:
        ledger = _load_ledger(ledger_path)
        outline = _load_outline(outline_path)
        document = _load_testcases(cases_path)
    except _DuplicateCoverageError as error:
        _duplicates_fail(error)
    except (OSError, ValueError, ValidationError, YAMLError) as error:
        _artifact_fail("test-case input", error)
    outline_findings = validate_outline(ledger, outline)
    findings = outline_findings + validate_testcases(ledger, outline, document)
    findings.sort(key=lambda item: (item.code, item.artifact_id, item.message))
    _findings_result(findings, "Test cases are valid")


@testcases_app.command("render")
def testcases_render(
    cases_path: Annotated[Path, typer.Argument(metavar="CASES")],
    output_path: Annotated[Path, typer.Option("--out")],
) -> None:
    """Render deterministic Markdown from an explicit test-case document."""
    try:
        _ensure_distinct_output(output_path, cases_path)
        document = _load_testcases(cases_path)
        markdown = render_testcases_markdown(document)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(output_path, markdown)
    except (OSError, ValueError, ValidationError, YAMLError) as error:
        _artifact_fail("test-case document", error)
    typer.echo(f"Rendered {output_path}")


@app.command("export")
def export_command(
    project_path: Annotated[Path, typer.Argument(metavar="PROJECT")],
    cases_path: Annotated[Path, typer.Argument(metavar="CASES")],
    profiles_root: Annotated[Path, typer.Option("--profiles-root")],
    profile_name: Annotated[str, typer.Option("--profile")],
    output_format: Annotated[ExportFormat, typer.Option("--format")],
    output_path: Annotated[Path, typer.Option("--out")],
    workbook_kind: Annotated[str | None, typer.Option("--workbook")] = None,
    project_name: Annotated[str | None, typer.Option("--project-name")] = None,
    artifact_name: Annotated[str | None, typer.Option("--artifact-name")] = None,
) -> None:
    """Export explicitly selected approved cases through an explicit profile root."""
    try:
        workspace = Workspace(project_path)
        document = _load_testcases(cases_path)
        profile = Profile.load(profile_name, profiles_root)
        protected = (cases_path, profile.root / "profile.yaml", workspace.state_path)
        if output_format is ExportFormat.MARKDOWN:
            result = export_markdown(
                workspace,
                document,
                profile,
                output_path,
                protected_inputs=protected,
            )
        else:
            if workbook_kind is None or project_name is None or artifact_name is None:
                raise ValueError(
                    "excel requires --workbook, --project-name, and --artifact-name"
                )
            result = export_excel(
                workspace,
                document,
                profile,
                workbook_kind=workbook_kind,
                output_directory=output_path,
                project=project_name,
                artifact=artifact_name,
                protected_inputs=protected,
            )
    except ProfileError as error:
        typer.echo(str(error))
        raise typer.Exit(code=1) from error
    except ExportError as error:
        _export_fail(error)
    except StateError as error:
        _fail(error)
    except (OSError, ValueError, ValidationError, YAMLError) as error:
        _artifact_fail("export input", error)
    typer.echo(f"Exported {result.case_count} cases to {result.path}")


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
    artifact_path: Annotated[Path | None, typer.Option("--artifact")] = None,
) -> None:
    """Approve a workspace gate."""
    workspace = _workspace(project_path)
    if stage is Stage.TESTCASES:
        if artifact_path is None:
            _fail(StateError("--artifact is required for testcase approval"))
        _approve_testcase_artifact(workspace, artifact_path)
        typer.echo("Approved testcases")
        return
    if artifact_path is not None:
        _fail(StateError("--artifact is only valid for testcases"))
    try:
        workspace.approve(stage)
    except StateError as error:
        _fail(error)
    typer.echo(f"Approved {stage.value}")


def _approve_testcase_artifact(workspace: Workspace, artifact_path: Path) -> None:
    expected_path = workspace.path / "tests" / "detailed" / "testcases.md"
    if artifact_path.resolve() != expected_path.resolve():
        _fail(StateError(f"testcase artifact must be {expected_path}"))
    try:
        original_content = artifact_path.read_text(encoding="utf-8")
        document = parse_testcases_markdown(original_content)
        ledger = _load_ledger(workspace.path / "coverage" / "ledger.yaml")
        outline = _load_outline(workspace.path / "tests" / "outlines" / "test-outline.yaml")
    except _DuplicateCoverageError as error:
        _duplicates_fail(error)
    except (OSError, ValueError, ValidationError, YAMLError) as error:
        _artifact_fail("testcase approval input", error)
    try:
        state = workspace.load_state()
    except StateError as error:
        _fail(error)
    if state.testcases is not ApprovalStatus.DRAFT:
        _fail(
            StateError(
                "testcases must be draft before approval; "
                f"current status is {state.testcases.value}"
            )
        )
    if document.status is not ApprovalStatus.DRAFT:
        _fail(StateError("testcase artifact must be draft before approval"))
    findings = validate_outline(ledger, outline) + validate_testcases(
        ledger, outline, document
    )
    findings.sort(key=lambda item: (item.code, item.artifact_id, item.message))
    if findings:
        for finding in findings:
            typer.echo(f"{finding.code} {finding.artifact_id}: {finding.message}")
        raise typer.Exit(code=1)
    approved_document = document.model_copy(update={"status": ApprovalStatus.APPROVED})
    approved_content = render_testcases_markdown(approved_document)
    try:
        workspace.approve_testcases_artifact(
            artifact_path,
            original_content,
            approved_content,
        )
    except StateError as error:
        _fail(error)


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


@app.command()
def reopen(
    stage: Stage,
    project_path: Annotated[Path, typer.Argument(metavar="[PATH]")] = Path("."),
) -> None:
    """Return an approved gate to draft for human-reviewed revision."""
    workspace = _workspace(project_path)
    try:
        workspace.reopen(stage)
    except StateError as error:
        _fail(error)
    typer.echo(f"Reopened {stage.value}")
