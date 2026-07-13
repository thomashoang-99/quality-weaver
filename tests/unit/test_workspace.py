import hashlib
import json

import pytest

from quality_weaver.models import ApprovalStatus
from quality_weaver.workspace import Stage, StateError, Workspace, sha256_file


def test_init_creates_exact_workspace_tree_and_initial_state(tmp_path) -> None:
    workspace = Workspace.init(tmp_path)

    assert workspace.path == tmp_path / ".quality-weaver"
    assert {
        path.relative_to(workspace.path).as_posix()
        for path in workspace.path.rglob("*")
    } == {
        "config.yaml",
        "state.json",
        "normalized",
        "questions",
        "coverage",
        "tests",
        "tests/outlines",
        "tests/detailed",
        "exports",
        "runs",
    }
    state = workspace.load_state()
    assert state.schema_version == 1
    assert state.requirements is ApprovalStatus.DRAFT
    assert state.coverage is ApprovalStatus.DRAFT
    assert state.testcases is ApprovalStatus.DRAFT
    assert state.upstream_hashes == {}
    assert state.last_run_id is None


def test_init_refuses_to_overwrite_existing_state(tmp_path) -> None:
    state_path = tmp_path / ".quality-weaver" / "state.json"
    state_path.parent.mkdir()
    state_path.write_text('{"sentinel": true}', encoding="utf-8")

    with pytest.raises(StateError, match="already exists"):
        Workspace.init(tmp_path)

    assert state_path.read_text(encoding="utf-8") == '{"sentinel": true}'


def test_load_state_rejects_unsupported_schema_version(tmp_path) -> None:
    workspace = Workspace.init(tmp_path)
    state = json.loads(workspace.state_path.read_text(encoding="utf-8"))
    state["schema_version"] = 2
    workspace.state_path.write_text(json.dumps(state), encoding="utf-8")

    with pytest.raises(StateError, match="invalid workspace state"):
        workspace.load_state()


def test_coverage_cannot_be_approved_before_requirements(tmp_path) -> None:
    workspace = Workspace.init(tmp_path)

    with pytest.raises(StateError, match="requirements must be approved"):
        workspace.approve(Stage.COVERAGE)


def test_testcases_cannot_be_approved_before_coverage(tmp_path) -> None:
    workspace = Workspace.init(tmp_path)
    workspace.approve(Stage.REQUIREMENTS)

    with pytest.raises(StateError, match="coverage must be approved"):
        workspace.approve(Stage.TESTCASES)


def test_gates_can_be_approved_in_order_and_become_export_ready(tmp_path) -> None:
    workspace = Workspace.init(tmp_path)

    workspace.approve(Stage.REQUIREMENTS)
    workspace.approve(Stage.COVERAGE)
    workspace.approve(Stage.TESTCASES)

    state = workspace.load_state()
    assert state.requirements is ApprovalStatus.APPROVED
    assert state.coverage is ApprovalStatus.APPROVED
    assert state.testcases is ApprovalStatus.APPROVED
    workspace.ensure_export_ready()


def test_export_readiness_requires_all_three_approved(tmp_path) -> None:
    workspace = Workspace.init(tmp_path)
    workspace.approve(Stage.REQUIREMENTS)
    workspace.approve(Stage.COVERAGE)

    with pytest.raises(StateError, match="all approval gates must be approved"):
        workspace.ensure_export_ready()


def test_upstream_change_marks_downstream_stale(tmp_path) -> None:
    workspace = Workspace.init(tmp_path)
    workspace.approve(Stage.REQUIREMENTS)
    workspace.approve(Stage.COVERAGE)
    workspace.invalidate_after(Stage.REQUIREMENTS)

    state = workspace.load_state()
    assert state.requirements is ApprovalStatus.APPROVED
    assert state.coverage is ApprovalStatus.STALE
    assert state.testcases is ApprovalStatus.STALE


def test_coverage_change_marks_only_testcases_stale(tmp_path) -> None:
    workspace = Workspace.init(tmp_path)
    workspace.approve(Stage.REQUIREMENTS)
    workspace.approve(Stage.COVERAGE)
    workspace.approve(Stage.TESTCASES)

    workspace.invalidate_after(Stage.COVERAGE)

    state = workspace.load_state()
    assert state.requirements is ApprovalStatus.APPROVED
    assert state.coverage is ApprovalStatus.APPROVED
    assert state.testcases is ApprovalStatus.STALE


def test_approve_persists_complete_json_without_leaving_temporary_file(tmp_path) -> None:
    workspace = Workspace.init(tmp_path)

    workspace.approve(Stage.REQUIREMENTS)

    raw_state = json.loads(workspace.state_path.read_text(encoding="utf-8"))
    assert raw_state["requirements"] == "approved"
    assert not workspace.state_path.with_suffix(".json.tmp").exists()


def test_sha256_file_hashes_bytes(tmp_path) -> None:
    source = tmp_path / "source.md"
    source.write_bytes(b"QualityWeaver\r\n")

    assert sha256_file(source) == hashlib.sha256(b"QualityWeaver\r\n").hexdigest()
