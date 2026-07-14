from collections.abc import Iterable
from pathlib import Path

import pytest
from typer.testing import CliRunner

import quality_weaver.testcases as testcase_module
from quality_weaver import models
from quality_weaver.cli import app
from quality_weaver.coverage import CoverageFinding
from quality_weaver.testcases import (
    render_testcases_markdown,
    validate_outline,
    validate_testcases,
)


def coverage_item(
    coverage_id: str,
    *,
    decision: models.CoverageDecision = models.CoverageDecision.INCLUDE,
    requirement_id: str = "REQ-LOGIN",
) -> models.CoverageItem:
    return models.CoverageItem(
        id=coverage_id,
        requirement_id=requirement_id,
        target_id="CTRL-EMAIL",
        viewpoint_id="VP-INPUT-VALIDATION-001",
        condition=coverage_id,
        decision=decision,
        priority="high",
        evidence="Requirement evidence",
        rationale="Test rationale",
        question_id=("Q-001" if decision is models.CoverageDecision.NEEDS_CLARIFICATION else None),
    )


def approved_ledger() -> models.CoverageLedger:
    return models.CoverageLedger(
        status=models.ApprovalStatus.APPROVED,
        catalog_version="1.0.0",
        items=[
            coverage_item("COV-001"),
            coverage_item("COV-002", requirement_id="REQ-SESSION"),
            coverage_item("COV-003", decision=models.CoverageDecision.EXCLUDE),
            coverage_item("COV-004", decision=models.CoverageDecision.NEEDS_CLARIFICATION),
        ],
    )


def approved_outline() -> models.TestOutline:
    return models.TestOutline(
        status=models.ApprovalStatus.APPROVED,
        items=[
            models.OutlineItem(id="OUT-001", title="Email", coverage_ids=["COV-001"]),
            models.OutlineItem(id="OUT-002", title="Session", coverage_ids=["COV-002"]),
        ],
    )


def single_item_outline() -> models.TestOutline:
    outline = approved_outline()
    return outline.model_copy(update={"items": outline.items[:1]})


def case(
    case_id: str = "TC-001",
    *,
    outline_id: str = "OUT-001",
    coverage_ids: list[str] | None = None,
    action: str = "Submit the form",
    expected: str = "A validation message appears",
    title: str = "Reject empty email",
) -> models.TestCase:
    return models.TestCase(
        id=case_id,
        title=title,
        outline_id=outline_id,
        coverage_ids=coverage_ids or ["COV-001"],
        preconditions=["User is on the login page"],
        test_data=["email = empty"],
        steps=[models.TestStep(action=action, expected=expected)],
        priority="high",
        tags=["login"],
    )


def finding_codes(findings: Iterable[CoverageFinding]) -> list[str]:
    return [finding.code for finding in findings]


def test_outline_cannot_reference_excluded_or_unresolved_coverage() -> None:
    outline = models.TestOutline(
        items=[
            models.OutlineItem(id="OUT-001", title="Invalid", coverage_ids=["COV-003", "COV-004"])
        ]
    )

    findings = validate_outline(approved_ledger(), outline)

    assert finding_codes(findings) == [
        "OUTLINE_COVERAGE_MISSING",
        "OUTLINE_COVERAGE_MISSING",
        "OUTLINE_COVERAGE_NOT_INCLUDED",
        "OUTLINE_COVERAGE_NOT_INCLUDED",
    ]
    assert all(finding.blocking for finding in findings)


def test_outline_rejects_unknown_missing_and_double_consumed_coverage() -> None:
    outline = models.TestOutline(
        items=[
            models.OutlineItem(
                id="OUT-001",
                title="One",
                coverage_ids=["COV-001", "COV-999"],
            ),
            models.OutlineItem(id="OUT-002", title="Two", coverage_ids=["COV-001"]),
        ]
    )

    assert finding_codes(validate_outline(approved_ledger(), outline)) == [
        "OUTLINE_COVERAGE_DUPLICATE",
        "OUTLINE_COVERAGE_MISSING",
        "OUTLINE_COVERAGE_UNKNOWN",
    ]


def test_testcases_require_known_outline_and_unique_case_ids() -> None:
    document = models.TestCaseDocument(
        cases=[
            case(),
            case(outline_id="OUT-999"),
        ]
    )

    assert finding_codes(validate_testcases(approved_ledger(), approved_outline(), document)) == [
        "TESTCASE_DUPLICATE_ID",
        "TESTCASE_OUTLINE_MISSING",
        "TESTCASE_UNKNOWN_OUTLINE",
    ]


def test_testcases_require_every_outline_item_to_have_a_detailed_case() -> None:
    document = models.TestCaseDocument(cases=[case()])

    assert finding_codes(validate_testcases(approved_ledger(), approved_outline(), document)) == [
        "TESTCASE_OUTLINE_MISSING"
    ]


def test_testcases_require_exact_outline_coverage_without_new_coverage() -> None:
    document = models.TestCaseDocument(cases=[case(coverage_ids=["COV-002", "COV-003"])])

    assert finding_codes(
        validate_testcases(approved_ledger(), single_item_outline(), document)
    ) == [
        "TESTCASE_COVERAGE_MISMATCH",
        "TESTCASE_COVERAGE_NOT_APPROVED",
        "TESTCASE_COVERAGE_NOT_APPROVED",
    ]


def test_testcase_steps_require_observable_action_and_expected_result() -> None:
    document = models.TestCaseDocument(cases=[case(action=" \r\n", expected="\t")])

    assert finding_codes(
        validate_testcases(approved_ledger(), single_item_outline(), document)
    ) == [
        "TESTCASE_ACTION_REQUIRED",
        "TESTCASE_EXPECTED_REQUIRED",
    ]


def test_markdown_is_canonical_inert_and_matches_golden() -> None:
    payload = (
        "pipe | next\r\n# heading <script>alert(1)</script> "
        "[link](javascript:alert(1)) **bold** `tick`"
    )
    document = models.TestCaseDocument(
        status=models.ApprovalStatus.APPROVED,
        cases=[
            case(
                "TC-002",
                outline_id="OUT-002",
                coverage_ids=["COV-002"],
                title="Session timeout",
            ),
            case(title=payload, action=payload, expected=payload),
        ],
    )

    rendered = render_testcases_markdown(document)

    expected = Path("tests/golden/expected/testcases.md").read_bytes()
    assert rendered.encode("utf-8") == expected
    assert rendered.index("## TC-001") < rendered.index("## TC-002")
    assert "pipe \\| next\\r\\n\\# heading" in rendered
    assert "<script>" not in rendered
    assert "javascript:" not in rendered
    assert "**bold**" not in rendered
    assert "`tick`" not in rendered
    assert "COV-001" in rendered


def test_markdown_neutralizes_leading_markers_in_numbered_dynamic_content() -> None:
    test_case = case().model_copy(
        update={
            "preconditions": ["- nested", "-"],
            "test_data": ["  + nested", "+"],
        }
    )

    rendered = render_testcases_markdown(models.TestCaseDocument(cases=[test_case]))

    assert "1. \\- nested" in rendered
    assert "2. \\-" in rendered
    assert "1.   \\+ nested" in rendered
    assert "2. \\+" in rendered


def test_markdown_roundtrip_preserves_every_testcase_field_and_comma_tags() -> None:
    payload = "line one\nline two\rbackslash \\ | <script> [x](javascript:y)"
    test_case = case(title=payload, action=payload, expected=payload).model_copy(
        update={
            "outline_id": "OUT-special,one",
            "coverage_ids": ["COV-001", "COV-special,one"],
            "preconditions": [payload, "- marker"],
            "test_data": ["key,value", "None."],
            "priority": "low",
            "tags": ["smoke,critical", payload],
        }
    )
    document = models.TestCaseDocument(
        status=models.ApprovalStatus.APPROVED,
        cases=[test_case],
    )

    rendered = render_testcases_markdown(document)
    parsed = testcase_module.parse_testcases_markdown(rendered)

    assert parsed == document
    assert render_testcases_markdown(parsed) == rendered
    assert "<script>" not in rendered
    assert "javascript:" not in rendered


@pytest.mark.parametrize(
    "mutate",
    [
        lambda text: text.replace("case_count: 1", "case_count: 2", 1),
        lambda text: text + "unexpected\n",
        lambda text: text.replace("| 1 |", "| 2 |", 1),
        lambda text: text.replace("- Priority: high", "- Priority: urgent", 1),
    ],
)
def test_markdown_parser_rejects_noncanonical_or_malformed_input(mutate) -> None:
    rendered = render_testcases_markdown(models.TestCaseDocument(cases=[case()]))

    with pytest.raises(testcase_module.TestCaseMarkdownError):
        testcase_module.parse_testcases_markdown(mutate(rendered))


def write_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    ledger_path = tmp_path / "ledger.yaml"
    outline_path = tmp_path / "outline.yaml"
    cases_path = tmp_path / "cases.yaml"
    ledger_path.write_text(approved_ledger().model_dump_json(), encoding="utf-8")
    outline_path.write_text(approved_outline().model_dump_json(), encoding="utf-8")
    cases_path.write_text(
        models.TestCaseDocument(
            cases=[case(), case("TC-002", outline_id="OUT-002", coverage_ids=["COV-002"])]
        ).model_dump_json(),
        encoding="utf-8",
    )
    return ledger_path, outline_path, cases_path


def test_cli_validates_outline_and_detailed_cases(tmp_path: Path) -> None:
    ledger_path, outline_path, cases_path = write_inputs(tmp_path)
    runner = CliRunner()

    outline_result = runner.invoke(
        app, ["outline", "validate", str(ledger_path), str(outline_path)]
    )
    cases_result = runner.invoke(
        app,
        [
            "testcases",
            "validate",
            str(ledger_path),
            str(outline_path),
            str(cases_path),
        ],
    )

    assert outline_result.exit_code == 0
    assert outline_result.stdout.strip() == "Outline is valid"
    assert cases_result.exit_code == 0
    assert cases_result.stdout.strip() == "Test cases are valid"


def test_cli_validates_canonical_markdown_cases(tmp_path: Path) -> None:
    ledger_path, outline_path, _ = write_inputs(tmp_path)
    document = models.TestCaseDocument(
        cases=[case(), case("TC-002", outline_id="OUT-002", coverage_ids=["COV-002"])]
    )
    cases_path = tmp_path / "cases.md"
    cases_path.write_text(render_testcases_markdown(document), encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "testcases",
            "validate",
            str(ledger_path),
            str(outline_path),
            str(cases_path),
        ],
    )

    assert result.exit_code == 0
    assert result.stdout.strip() == "Test cases are valid"


def test_cli_renders_atomically_and_rejects_resolved_input_collision(
    tmp_path: Path,
) -> None:
    _, _, cases_path = write_inputs(tmp_path)
    output_path = tmp_path / "out" / "testcases.md"
    runner = CliRunner()

    rendered = runner.invoke(
        app, ["testcases", "render", str(cases_path), "--out", str(output_path)]
    )
    collision = runner.invoke(
        app,
        [
            "testcases",
            "render",
            str(cases_path),
            "--out",
            str(tmp_path / "alias" / ".." / cases_path.name),
        ],
    )

    assert rendered.exit_code == 0
    assert output_path.read_text(encoding="utf-8").startswith("---\n")
    assert collision.exit_code == 1
    assert "output path" in collision.stdout


def test_cli_validation_failure_is_concise(tmp_path: Path) -> None:
    ledger_path, outline_path, _ = write_inputs(tmp_path)
    outline_path.write_text(
        models.TestOutline(
            items=[models.OutlineItem(id="OUT-001", title="Bad", coverage_ids=["COV-003"])]
        ).model_dump_json(),
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["outline", "validate", str(ledger_path), str(outline_path)])

    assert result.exit_code == 1
    assert "OUTLINE_COVERAGE_NOT_INCLUDED COV-003" in result.stdout
    assert "Traceback" not in result.stdout
