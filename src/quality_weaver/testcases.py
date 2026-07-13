from collections import Counter

from quality_weaver.coverage import CoverageFinding
from quality_weaver.models import (
    CoverageDecision,
    CoverageLedger,
    TestCaseDocument,
    TestOutline,
)
from quality_weaver.testmap import _markdown_text


def validate_outline(ledger: CoverageLedger, outline: TestOutline) -> list[CoverageFinding]:
    """Require an outline to consume every included coverage item exactly once."""
    findings: list[CoverageFinding] = []
    ledger_by_id = {item.id: item for item in ledger.items}
    consumption = Counter(
        coverage_id for outline_item in outline.items for coverage_id in outline_item.coverage_ids
    )

    for outline_id, count in Counter(item.id for item in outline.items).items():
        if count > 1:
            findings.append(
                CoverageFinding(
                    code="OUTLINE_DUPLICATE_ID",
                    message="Outline ID is duplicated",
                    artifact_id=outline_id,
                )
            )

    for coverage_id, count in consumption.items():
        coverage = ledger_by_id.get(coverage_id)
        if coverage is None:
            findings.append(
                CoverageFinding(
                    code="OUTLINE_COVERAGE_UNKNOWN",
                    message="Outline references unknown coverage",
                    artifact_id=coverage_id,
                )
            )
        elif coverage.decision is not CoverageDecision.INCLUDE:
            findings.append(
                CoverageFinding(
                    code="OUTLINE_COVERAGE_NOT_INCLUDED",
                    message="Outline coverage is excluded or unresolved",
                    artifact_id=coverage_id,
                )
            )
        elif count > 1:
            findings.append(
                CoverageFinding(
                    code="OUTLINE_COVERAGE_DUPLICATE",
                    message=f"Included coverage is consumed {count} times",
                    artifact_id=coverage_id,
                )
            )

    for coverage in ledger.items:
        if coverage.decision is CoverageDecision.INCLUDE and consumption[coverage.id] == 0:
            findings.append(
                CoverageFinding(
                    code="OUTLINE_COVERAGE_MISSING",
                    message="Included coverage is missing from the outline",
                    artifact_id=coverage.id,
                )
            )
    return _sorted(findings)


def validate_testcases(
    ledger: CoverageLedger,
    outline: TestOutline,
    document: TestCaseDocument,
) -> list[CoverageFinding]:
    """Validate detailed cases against their approved outline and coverage ledger."""
    findings: list[CoverageFinding] = []
    outline_by_id = {item.id: item for item in outline.items}
    included_coverage = {
        item.id for item in ledger.items if item.decision is CoverageDecision.INCLUDE
    }
    outlined_coverage = {coverage_id for item in outline.items for coverage_id in item.coverage_ids}
    approved_coverage = included_coverage & outlined_coverage
    referenced_outline_ids = {test_case.outline_id for test_case in document.cases}

    for outline_id in sorted(set(outline_by_id) - referenced_outline_ids):
        findings.append(
            CoverageFinding(
                code="TESTCASE_OUTLINE_MISSING",
                message="Outline item has no detailed test case",
                artifact_id=outline_id,
            )
        )

    for case_id, count in Counter(case.id for case in document.cases).items():
        if count > 1:
            findings.append(
                CoverageFinding(
                    code="TESTCASE_DUPLICATE_ID",
                    message="Test case ID is duplicated",
                    artifact_id=case_id,
                )
            )

    for test_case in document.cases:
        outline_item = outline_by_id.get(test_case.outline_id)
        if outline_item is None:
            findings.append(
                CoverageFinding(
                    code="TESTCASE_UNKNOWN_OUTLINE",
                    message=f"Unknown outline ID: {test_case.outline_id}",
                    artifact_id=test_case.id,
                )
            )
        elif Counter(test_case.coverage_ids) != Counter(outline_item.coverage_ids):
            findings.append(
                CoverageFinding(
                    code="TESTCASE_COVERAGE_MISMATCH",
                    message="Test case coverage must exactly match its outline item",
                    artifact_id=test_case.id,
                )
            )

        for coverage_id in sorted(set(test_case.coverage_ids) - approved_coverage):
            findings.append(
                CoverageFinding(
                    code="TESTCASE_COVERAGE_NOT_APPROVED",
                    message="Test case introduces coverage not approved by the outline",
                    artifact_id=coverage_id,
                )
            )

        for step_number, step in enumerate(test_case.steps, start=1):
            if not step.action.strip():
                findings.append(
                    CoverageFinding(
                        code="TESTCASE_ACTION_REQUIRED",
                        message=f"Step {step_number} requires an observable action",
                        artifact_id=test_case.id,
                    )
                )
            if not step.expected.strip():
                findings.append(
                    CoverageFinding(
                        code="TESTCASE_EXPECTED_REQUIRED",
                        message=f"Step {step_number} requires an observable expected result",
                        artifact_id=test_case.id,
                    )
                )
    return _sorted(findings)


def render_testcases_markdown(document: TestCaseDocument) -> str:
    """Render canonical, inert Markdown for a detailed test-case document."""
    cases = sorted(document.cases, key=lambda item: item.id)
    lines = [
        "---",
        f"status: {document.status.value}",
        f"case_count: {len(cases)}",
        "---",
        "# Test Cases",
    ]
    for test_case in cases:
        coverage = ", ".join(
            _markdown_text(coverage_id) for coverage_id in sorted(test_case.coverage_ids)
        )
        tags = ", ".join(_markdown_text(tag) for tag in sorted(test_case.tags))
        lines.extend(
            [
                "",
                f"## {test_case.id}: {_markdown_text(test_case.title)}",
                "",
                f"- Requirement traceability: via {_markdown_text(test_case.outline_id)}",
                f"- Coverage: {coverage}",
                f"- Priority: {test_case.priority}",
                f"- Tags: {tags if tags else 'None.'}",
                "",
                "### Preconditions",
                "",
                *_numbered_or_none(test_case.preconditions),
                "",
                "### Test Data",
                "",
                *_numbered_or_none(test_case.test_data),
                "",
                "### Steps",
                "",
                "| Step | Action | Expected Result |",
                "| ---: | --- | --- |",
            ]
        )
        for number, step in enumerate(test_case.steps, start=1):
            lines.append(
                f"| {number} | {_markdown_text(step.action)} | {_markdown_text(step.expected)} |"
            )
    return "\n".join(lines) + "\n"


def _numbered_or_none(values: list[str]) -> list[str]:
    if not values:
        return ["None."]
    return [f"{number}. {_list_text(value)}" for number, value in enumerate(values, 1)]


def _list_text(value: str) -> str:
    escaped = _markdown_text(value)
    leading_length = len(escaped) - len(escaped.lstrip())
    body = escaped[leading_length:]
    if body and body[0] in "-+" and (len(body) == 1 or body[1].isspace()):
        return f"{escaped[:leading_length]}\\{body}"
    return escaped


def _sorted(findings: list[CoverageFinding]) -> list[CoverageFinding]:
    return sorted(findings, key=lambda item: (item.code, item.artifact_id, item.message))
