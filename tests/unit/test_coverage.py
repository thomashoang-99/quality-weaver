from pathlib import Path

from quality_weaver.catalog import Catalog
from quality_weaver.coverage import validate_ledger, validate_outline_consumption
from quality_weaver.models import (
    ApprovalStatus,
    CoverageDecision,
    CoverageItem,
    CoverageLedger,
    OutlineItem,
)
from quality_weaver.models import (
    TestOutline as Outline,
)

CATALOG = Catalog.load(Path("viewpoints"))
VIEWPOINT_ID = "VP-INPUT-VALIDATION-001"


def ledger_with(**updates: object) -> CoverageLedger:
    item = CoverageItem(
        id="COV-001",
        requirement_id="REQ-LOGIN",
        target_id="CTRL-EMAIL",
        viewpoint_id=VIEWPOINT_ID,
        condition="empty",
        decision=CoverageDecision.INCLUDE,
        priority="high",
        evidence="Email is required",
        rationale="Required input",
    ).model_copy(update=updates)
    return CoverageLedger(catalog_version=CATALOG.version, items=[item])


def finding_codes(ledger: CoverageLedger, **kwargs: object) -> list[str]:
    return [finding.code for finding in validate_ledger(ledger, **kwargs)]


def test_clarification_requires_question_id() -> None:
    ledger = ledger_with(decision=CoverageDecision.NEEDS_CLARIFICATION, question_id=None)

    assert finding_codes(ledger) == ["COVERAGE_QUESTION_REQUIRED"]


def test_duplicate_logical_key_is_reported() -> None:
    item = ledger_with().items[0]
    duplicate = item.model_copy(update={"id": "COV-002"})
    ledger = CoverageLedger.model_construct(
        status=ApprovalStatus.DRAFT,
        catalog_version=CATALOG.version,
        profile="generic",
        items=[item, duplicate],
    )

    assert finding_codes(ledger) == ["COVERAGE_DUPLICATE_KEY"]


def test_unknown_requirement_is_reported_from_explicit_ids() -> None:
    assert finding_codes(ledger_with(), known_requirement_ids={"REQ-OTHER"}) == [
        "COVERAGE_UNKNOWN_REQUIREMENT"
    ]


def test_unknown_target_is_reported_from_explicit_ids() -> None:
    assert finding_codes(
        ledger_with(), known_target_ids={"REQ-LOGIN": {"CTRL-PASSWORD"}}
    ) == [
        "COVERAGE_UNKNOWN_TARGET"
    ]


def test_target_must_belong_to_its_requirement() -> None:
    assert finding_codes(
        ledger_with(),
        known_target_ids={"REQ-LOGIN": set(), "REQ-OTHER": {"CTRL-EMAIL"}},
    ) == ["COVERAGE_UNKNOWN_TARGET"]


def test_unknown_viewpoint_is_reported_from_explicit_catalog() -> None:
    ledger = ledger_with(viewpoint_id="VP-NOT-THERE")

    assert finding_codes(ledger, catalog=CATALOG) == ["COVERAGE_UNKNOWN_VIEWPOINT"]


def test_catalog_version_must_match_ledger() -> None:
    ledger = ledger_with().model_copy(update={"catalog_version": "0.9.0"})

    assert finding_codes(ledger, catalog=CATALOG) == [
        "COVERAGE_CATALOG_VERSION_MISMATCH"
    ]


def test_evidence_is_required() -> None:
    assert finding_codes(ledger_with(evidence="  ")) == ["COVERAGE_EVIDENCE_REQUIRED"]


def test_clarification_with_question_remains_unresolved() -> None:
    ledger = ledger_with(
        decision=CoverageDecision.NEEDS_CLARIFICATION,
        question_id="Q-001",
    )

    assert finding_codes(ledger) == ["COVERAGE_UNRESOLVED"]


def test_findings_are_typed_blocking_and_deterministically_ordered() -> None:
    ledger = ledger_with(evidence="", requirement_id="REQ-UNKNOWN")

    findings = validate_ledger(ledger, known_requirement_ids={"REQ-LOGIN"})

    assert [(item.code, item.artifact_id, item.blocking) for item in findings] == [
        ("COVERAGE_EVIDENCE_REQUIRED", "COV-001", True),
        ("COVERAGE_UNKNOWN_REQUIREMENT", "COV-001", True),
    ]
    assert all(item.message for item in findings)


def test_included_coverage_must_be_consumed_once() -> None:
    findings = validate_outline_consumption(ledger_with(), Outline(items=[]))

    assert [item.code for item in findings] == ["COVERAGE_NOT_CONSUMED"]


def test_included_coverage_cannot_be_consumed_twice() -> None:
    outline = Outline(
        items=[
            OutlineItem(id="OUT-001", title="One", coverage_ids=["COV-001"]),
            OutlineItem(id="OUT-002", title="Two", coverage_ids=["COV-001"]),
        ]
    )

    findings = validate_outline_consumption(ledger_with(), outline)

    assert [item.code for item in findings] == ["COVERAGE_CONSUMED_TWICE"]


def test_excluded_and_unresolved_coverage_are_not_outline_obligations() -> None:
    excluded = ledger_with(decision=CoverageDecision.EXCLUDE)
    unresolved = ledger_with(
        decision=CoverageDecision.NEEDS_CLARIFICATION,
        question_id="Q-001",
    )

    assert validate_outline_consumption(excluded, Outline(items=[])) == []
    assert validate_outline_consumption(unresolved, Outline(items=[])) == []
