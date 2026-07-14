from pathlib import Path

from ruamel.yaml import YAML

from quality_weaver.catalog import Catalog
from quality_weaver.coverage import validate_ledger
from quality_weaver.io import atomic_write_text
from quality_weaver.models import (
    ApprovalStatus,
    CoverageLedger,
    RequirementDocument,
    TestCaseDocument,
    TestOutline,
)
from quality_weaver.testcases import (
    render_testcases_markdown,
    validate_outline,
    validate_testcases,
)
from quality_weaver.testmap import render_testmap
from quality_weaver.workspace import Stage, Workspace

_GOLDEN = Path("tests/golden/login")
_VIEWPOINTS = Path("viewpoints")
_KNOWN_REQUIREMENT_IDS = {"REQ-LOGIN"}
_KNOWN_TARGET_IDS = {"REQ-LOGIN": {"CTRL-EMAIL", "CTRL-SUBMIT"}}
_yaml = YAML(typ="safe")


def _load(path: Path) -> object:
    return _yaml.load(path.read_text(encoding="utf-8"))


def test_login_vertical_slice(tmp_path: Path) -> None:
    workspace = Workspace.init(tmp_path)
    catalog = Catalog.load(_VIEWPOINTS)

    requirement = RequirementDocument.model_validate(_load(_GOLDEN / "normalized.yaml"))
    atomic_write_text(
        workspace.path / "normalized" / "requirements.yaml",
        (_GOLDEN / "normalized.yaml").read_text(encoding="utf-8"),
    )
    assert requirement.id in _KNOWN_REQUIREMENT_IDS

    ledger = CoverageLedger.model_validate(_load(_GOLDEN / "ledger.yaml"))
    coverage_findings = validate_ledger(
        ledger,
        known_requirement_ids=_KNOWN_REQUIREMENT_IDS,
        known_target_ids=_KNOWN_TARGET_IDS,
        catalog=catalog,
    )
    assert coverage_findings == []
    atomic_write_text(
        workspace.path / "coverage" / "ledger.yaml",
        (_GOLDEN / "ledger.yaml").read_text(encoding="utf-8"),
    )

    test_map = render_testmap(
        ledger,
        catalog,
        known_requirement_ids=_KNOWN_REQUIREMENT_IDS,
        known_target_ids=_KNOWN_TARGET_IDS,
    )
    assert test_map.encode("utf-8") == (_GOLDEN / "test-map.md").read_bytes()

    workspace.approve(Stage.REQUIREMENTS)
    workspace.approve(Stage.COVERAGE)

    outline = TestOutline.model_validate(_load(_GOLDEN / "outline.yaml"))
    assert validate_outline(ledger, outline) == []

    approved_cases = TestCaseDocument.model_validate(_load(_GOLDEN / "testcases.yaml"))
    assert approved_cases.status is ApprovalStatus.APPROVED
    assert validate_testcases(ledger, outline, approved_cases) == []

    draft_cases = approved_cases.model_copy(update={"status": ApprovalStatus.DRAFT})
    draft_markdown = render_testcases_markdown(draft_cases)
    artifact_path = workspace.path / "tests" / "detailed" / "testcases.md"
    atomic_write_text(artifact_path, draft_markdown)

    approved_markdown = render_testcases_markdown(approved_cases)
    workspace.approve_testcases_artifact(artifact_path, draft_markdown, approved_markdown)

    assert artifact_path.read_bytes() == (_GOLDEN / "testcases.md").read_bytes()

    state = workspace.load_state()
    assert state.requirements is ApprovalStatus.APPROVED
    assert state.coverage is ApprovalStatus.APPROVED
    assert state.testcases is ApprovalStatus.APPROVED
    workspace.ensure_export_ready()
