import pytest
from typer.testing import CliRunner

from quality_weaver.cli import app
from quality_weaver.models import ApprovalStatus, RequirementDocument, RequirementEntity
from quality_weaver.workspace import Stage, Workspace


def test_version_command() -> None:
    result = CliRunner().invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "quality-weaver 0.1.0"


def test_init_status_and_approve_commands(tmp_path) -> None:
    runner = CliRunner()

    initialized = runner.invoke(app, ["init", str(tmp_path)])
    assert initialized.exit_code == 0
    assert "Initialized" in initialized.stdout

    status = runner.invoke(app, ["status", str(tmp_path)])
    assert status.exit_code == 0
    assert "requirements  draft" in status.stdout
    assert "coverage      draft" in status.stdout
    assert "testcases     draft" in status.stdout
    assert "Next: approve requirements" in status.stdout

    approved = runner.invoke(app, ["approve", "requirements", str(tmp_path)])
    assert approved.exit_code == 0
    assert "Approved requirements" in approved.stdout

    status = runner.invoke(app, ["status", str(tmp_path)])
    assert "requirements  approved" in status.stdout
    assert "Next: approve coverage" in status.stdout


def test_init_command_reports_existing_workspace(tmp_path) -> None:
    runner = CliRunner()
    assert runner.invoke(app, ["init", str(tmp_path)]).exit_code == 0

    duplicate = runner.invoke(app, ["init", str(tmp_path)])

    assert duplicate.exit_code == 1
    assert "already exists" in duplicate.stdout


def test_regenerate_command_recovers_stale_coverage(tmp_path) -> None:
    workspace = Workspace.init(tmp_path)
    workspace.approve(Stage.REQUIREMENTS)
    workspace.approve(Stage.COVERAGE)
    workspace.invalidate_after(Stage.REQUIREMENTS)

    result = CliRunner().invoke(app, ["regenerate", "coverage", str(tmp_path)])

    assert result.exit_code == 0
    assert "Ready to regenerate coverage" in result.stdout
    assert workspace.load_state().coverage is ApprovalStatus.DRAFT


def test_status_uses_one_state_snapshot(tmp_path, monkeypatch) -> None:
    Workspace.init(tmp_path)
    original_load_state = Workspace.load_state
    calls = 0

    def counted_load_state(workspace: Workspace):
        nonlocal calls
        calls += 1
        return original_load_state(workspace)

    monkeypatch.setattr(Workspace, "load_state", counted_load_state)

    result = CliRunner().invoke(app, ["status", str(tmp_path)])

    assert result.exit_code == 0
    assert calls == 1


def test_requirements_validate_accepts_strict_requirement_document(tmp_path) -> None:
    requirement = RequirementDocument(
        id="REQ-LOGIN",
        title="Login",
        source_path="requirements/login.md",
        source_sha256="a" * 64,
        entities=[
            RequirementEntity(
                id="CTRL-EMAIL",
                type="input",
                name="Email",
                source_quote="Email is required",
            )
        ],
    )
    path = tmp_path / "requirement.yaml"
    path.write_text(requirement.model_dump_json(), encoding="utf-8")

    result = CliRunner().invoke(app, ["requirements", "validate", str(path)])

    assert result.exit_code == 0
    assert result.stdout.strip() == "Requirement document is valid"


@pytest.mark.parametrize(
    "content",
    [
        "id: REQ-BAD\nunknown: true\n",
        "id: REQ-ONE\nid: REQ-TWO\n",
    ],
)
def test_requirements_validate_reports_typed_concise_failure(
    tmp_path, content: str
) -> None:
    path = tmp_path / "requirement.yaml"
    path.write_text(content, encoding="utf-8")

    result = CliRunner().invoke(app, ["requirements", "validate", str(path)])

    assert result.exit_code == 1
    assert result.stdout.startswith("Invalid requirement document:")
    assert "Traceback" not in result.stdout


def test_requirements_validate_is_discoverable_at_nested_help() -> None:
    runner = CliRunner()

    root = runner.invoke(app, ["--help"])
    group = runner.invoke(app, ["requirements", "--help"])
    leaf = runner.invoke(app, ["requirements", "validate", "--help"])

    assert "requirements" in root.stdout
    assert "validate" in group.stdout
    assert "PATH" in leaf.stdout


def test_reopen_command_returns_approved_gate_to_human_review(tmp_path) -> None:
    workspace = Workspace.init(tmp_path)
    workspace.approve(Stage.REQUIREMENTS)
    workspace.approve(Stage.COVERAGE)
    workspace.approve(Stage.TESTCASES)

    result = CliRunner().invoke(app, ["reopen", "coverage", str(tmp_path)])

    assert result.exit_code == 0
    assert result.stdout.strip() == "Reopened coverage"
    state = workspace.load_state()
    assert state.requirements is ApprovalStatus.APPROVED
    assert state.coverage is ApprovalStatus.DRAFT
    assert state.testcases is ApprovalStatus.STALE


def test_reopen_command_rejects_nonapproved_gate_concisely(tmp_path) -> None:
    Workspace.init(tmp_path)

    result = CliRunner().invoke(app, ["reopen", "coverage", str(tmp_path)])

    assert result.exit_code == 1
    assert "coverage must be approved before reopening" in result.stdout
    assert "Traceback" not in result.stdout
