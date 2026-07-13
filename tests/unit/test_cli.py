from typer.testing import CliRunner

from quality_weaver.cli import app
from quality_weaver.models import ApprovalStatus
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
