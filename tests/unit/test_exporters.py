from hashlib import sha256
from pathlib import Path

import openpyxl
import pytest
from typer.testing import CliRunner

from quality_weaver import exporters as exporter_module
from quality_weaver.cli import app
from quality_weaver.exporters import ExportError, export_excel, export_markdown
from quality_weaver.models import (
    ApprovalStatus,
)
from quality_weaver.models import (
    TestCase as CaseModel,
)
from quality_weaver.models import (
    TestCaseDocument as CaseDocument,
)
from quality_weaver.models import (
    TestStep as StepModel,
)
from quality_weaver.profiles import Profile
from quality_weaver.testcases import render_testcases_markdown
from quality_weaver.workspace import Stage, Workspace

PROFILES_ROOT = Path("profiles")


def document(*, status: ApprovalStatus = ApprovalStatus.APPROVED) -> CaseDocument:
    return CaseDocument(
        status=status,
        cases=[
            CaseModel(
                id="TC-002",
                title="Session timeout",
                outline_id="OUT-002",
                coverage_ids=["COV-002"],
                preconditions=["User is signed in"],
                test_data=[],
                steps=[StepModel(action="Wait for timeout", expected="Session expires")],
                priority="medium",
                tags=["session"],
            ),
            CaseModel(
                id="TC-001",
                title="Reject empty email",
                outline_id="OUT-001",
                coverage_ids=["COV-001", "COV-003"],
                preconditions=["User is on login", "Form is empty"],
                test_data=["email = empty"],
                steps=[
                    StepModel(action="Submit form", expected="Validation appears"),
                    StepModel(action="Inspect email", expected="Email stays empty"),
                ],
                priority="high",
                tags=["login"],
            ),
        ],
    )


def ready_workspace(tmp_path: Path) -> Workspace:
    workspace = Workspace.init(tmp_path)
    for stage in Stage:
        workspace.approve(stage)
    return workspace


def sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("approved_count", [0, 1, 2])
def test_export_is_blocked_until_all_three_workspace_gates_are_approved(
    tmp_path: Path, approved_count: int
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    workspace = Workspace.init(project)
    for stage in list(Stage)[:approved_count]:
        workspace.approve(stage)

    with pytest.raises(ExportError) as raised:
        export_markdown(
            workspace,
            document(),
            Profile.load("generic", PROFILES_ROOT),
            tmp_path / "out" / "testcases.md",
            protected_inputs=(),
        )

    assert raised.value.findings[0].code == "EXPORT_GATES_NOT_APPROVED"
    assert not (tmp_path / "out" / "testcases.md").exists()


def test_export_requires_approved_document_and_compatible_format(tmp_path: Path) -> None:
    workspace = ready_workspace(tmp_path)
    generic = Profile.load("generic", PROFILES_ROOT)

    with pytest.raises(ExportError) as unapproved:
        export_markdown(
            workspace,
            document(status=ApprovalStatus.DRAFT),
            generic,
            tmp_path / "draft.md",
            protected_inputs=(),
        )
    with pytest.raises(ExportError) as incompatible:
        export_excel(
            workspace,
            document(),
            generic,
            workbook_kind="ut",
            output_directory=tmp_path,
            project="Demo",
            artifact="Login",
            protected_inputs=(),
        )

    assert unapproved.value.findings[0].code == "EXPORT_CASES_NOT_APPROVED"
    assert incompatible.value.findings[0].code == "EXPORT_FORMAT_UNSUPPORTED"


def test_generic_markdown_export_is_canonical_byte_for_byte_and_atomic(tmp_path: Path) -> None:
    workspace = ready_workspace(tmp_path)
    output = tmp_path / "exports" / "testcases.md"

    result = export_markdown(
        workspace,
        document(),
        Profile.load("generic", PROFILES_ROOT),
        output,
        protected_inputs=(),
    )

    assert result.path == output
    assert result.case_count == 2
    assert output.read_bytes() == render_testcases_markdown(document()).encode("utf-8")
    assert list(output.parent.glob(".testcases.md.*.tmp")) == []


def test_resolved_output_collision_is_rejected_before_write(tmp_path: Path) -> None:
    workspace = ready_workspace(tmp_path)
    cases_path = tmp_path / "cases.yaml"
    cases_path.write_text(document().model_dump_json(), encoding="utf-8")

    with pytest.raises(ExportError) as raised:
        export_markdown(
            workspace,
            document(),
            Profile.load("generic", PROFILES_ROOT),
            tmp_path / "alias" / ".." / "cases.yaml",
            protected_inputs=(cases_path,),
        )

    assert raised.value.findings[0].code == "EXPORT_OUTPUT_COLLISION"
    assert cases_path.read_text(encoding="utf-8") == document().model_dump_json()


@pytest.mark.parametrize(
    "kind, expected_name",
    [
        ("ut", "Demo_Login_Test Case UT.xlsx"),
        ("it", "Demo_Login_Test Case IT.xlsx"),
    ],
)
def test_excel_export_preserves_template_maps_cases_and_verifies_count(
    tmp_path: Path, kind: str, expected_name: str
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    workspace = ready_workspace(project)
    profile = Profile.load("company-legacy", PROFILES_ROOT)
    template = profile.workbooks[kind].template_path(profile.root)
    before = sha256_file(template)

    result = export_excel(
        workspace,
        document(),
        profile,
        workbook_kind=kind,
        output_directory=tmp_path / "exports",
        project="Demo",
        artifact="Login",
        protected_inputs=(),
    )

    assert result.path.name == expected_name
    assert result.case_count == 2
    assert sha256_file(template) == before
    workbook = openpyxl.load_workbook(result.path, data_only=False)
    sheet = workbook["Testcase"]
    assert sheet["A16"].value == "TC-001"
    assert sheet["B16"].value == "Reject empty email"
    assert sheet["D16"].value == "Outline: OUT-001\nCoverage: COV-001, COV-003\nPriority: high"
    assert sheet["G16"].value == "1. User is on login\n2. Form is empty"
    assert sheet["I16"].value == "1. Submit form\n2. Inspect email"
    assert sheet["J16"].value == "1. Validation appears\n2. Email stays empty"
    assert sheet["A17"].value == "TC-002"
    assert list(result.path.parent.glob(f".{expected_name}.*.tmp")) == []


def test_excel_rejects_unknown_workbook_missing_sheet_and_unsafe_filename(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    workspace = ready_workspace(project)
    profile = Profile.load("company-legacy", PROFILES_ROOT)

    with pytest.raises(ExportError) as unknown:
        export_excel(
            workspace,
            document(),
            profile,
            workbook_kind="e2e",
            output_directory=tmp_path,
            project="Demo",
            artifact="Login",
            protected_inputs=(),
        )
    with pytest.raises(ExportError) as unsafe:
        export_excel(
            workspace,
            document(),
            profile,
            workbook_kind="ut",
            output_directory=tmp_path,
            project="../Demo",
            artifact="Login",
            protected_inputs=(),
        )

    assert unknown.value.findings[0].code == "EXPORT_WORKBOOK_UNKNOWN"
    assert unsafe.value.findings[0].code == "EXPORT_FILENAME_VALUE_INVALID"

    workbook_profile = profile.workbooks["ut"].model_copy(
        update={"required_sheets": ("Testcase", "Missing")}
    )
    broken = profile.model_copy(update={"workbooks": {"ut": workbook_profile}})
    with pytest.raises(ExportError) as missing:
        export_excel(
            workspace,
            document(),
            broken,
            workbook_kind="ut",
            output_directory=tmp_path,
            project="Demo",
            artifact="Login",
            protected_inputs=(),
        )
    assert missing.value.findings[0].code == "EXPORT_TEMPLATE_SHEET_MISSING"


def test_excel_rejects_template_whose_declared_column_header_changed(
    tmp_path: Path, monkeypatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    workspace = ready_workspace(project)
    profile = Profile.load("company-legacy", PROFILES_ROOT)
    original_load = exporter_module.openpyxl.load_workbook

    def load_with_wrong_header(*args, **kwargs):
        workbook = original_load(*args, **kwargs)
        workbook["Testcase"]["A12"] = "Unexpected ID header"
        return workbook

    monkeypatch.setattr(exporter_module.openpyxl, "load_workbook", load_with_wrong_header)

    with pytest.raises(ExportError) as raised:
        export_excel(
            workspace,
            document(),
            profile,
            workbook_kind="ut",
            output_directory=tmp_path,
            project="Demo",
            artifact="Login",
            protected_inputs=(),
        )

    assert raised.value.findings[0].code == "EXPORT_TEMPLATE_MAPPING_INVALID"


def test_excel_writes_user_text_as_literal_cells_not_formulas(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    workspace = ready_workspace(project)
    profile = Profile.load("company-legacy", PROFILES_ROOT)
    cases = document()
    cases.cases[1].title = "=1+1"

    result = export_excel(
        workspace,
        cases,
        profile,
        workbook_kind="ut",
        output_directory=tmp_path,
        project="Demo",
        artifact="Formula",
        protected_inputs=(),
    )

    cell = openpyxl.load_workbook(result.path, data_only=False)["Testcase"]["B16"]
    assert cell.value == "=1+1"
    assert cell.data_type == "s"


def test_cli_export_uses_only_explicit_project_cases_profile_and_output_paths(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    ready_workspace(project)
    cases_path = tmp_path / "selected-cases.yaml"
    cases_path.write_text(document().model_dump_json(), encoding="utf-8")
    output = tmp_path / "selected-output.md"

    result = CliRunner().invoke(
        app,
        [
            "export",
            str(project),
            str(cases_path),
            "--profiles-root",
            str(PROFILES_ROOT.resolve()),
            "--profile",
            "generic",
            "--format",
            "markdown",
            "--out",
            str(output),
        ],
    )

    assert result.exit_code == 0
    assert result.stdout.strip() == f"Exported 2 cases to {output}"
    assert output.read_bytes() == render_testcases_markdown(document()).encode("utf-8")


def test_cli_unknown_profile_and_format_fail_concisely(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    ready_workspace(project)
    cases_path = tmp_path / "cases.yaml"
    cases_path.write_text(document().model_dump_json(), encoding="utf-8")
    runner = CliRunner()

    unknown_profile = runner.invoke(
        app,
        [
            "export",
            str(project),
            str(cases_path),
            "--profiles-root",
            str(PROFILES_ROOT.resolve()),
            "--profile",
            "missing",
            "--format",
            "markdown",
            "--out",
            str(tmp_path / "out.md"),
        ],
    )
    unknown_format = runner.invoke(
        app,
        [
            "export",
            str(project),
            str(cases_path),
            "--profiles-root",
            str(PROFILES_ROOT.resolve()),
            "--profile",
            "generic",
            "--format",
            "pdf",
            "--out",
            str(tmp_path / "out.pdf"),
        ],
    )

    assert unknown_profile.exit_code == 1
    assert "PROFILE_UNKNOWN" in unknown_profile.stdout
    assert unknown_format.exit_code != 0
    assert "Invalid value" in unknown_format.stderr
    assert "Traceback" not in unknown_profile.stdout + unknown_format.stderr
