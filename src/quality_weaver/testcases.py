import html
import json
import re
from collections import Counter
from typing import Literal, cast

from pydantic import ValidationError

from quality_weaver.coverage import CoverageFinding
from quality_weaver.models import (
    ApprovalStatus,
    CoverageDecision,
    CoverageLedger,
    TestCase,
    TestCaseDocument,
    TestOutline,
    TestStep,
)

_MARKDOWN_PUNCTUATION = frozenset("`*{}[]()#!|:~.@_")


class TestCaseMarkdownError(ValueError):
    """Raised when canonical testcase Markdown is malformed or noncanonical."""


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
        coverage = _render_list(sorted(test_case.coverage_ids))
        tags = _render_list(sorted(test_case.tags))
        lines.extend(
            [
                "",
                f"## {test_case.id}: {_markdown_text(test_case.title)}",
                "",
                f"- Requirement traceability: via {_markdown_text(test_case.outline_id)}",
                f"- Coverage: {coverage}",
                f"- Priority: {test_case.priority}",
                f"- Tags: {tags}",
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


def parse_testcases_markdown(text: str) -> TestCaseDocument:
    """Parse only the exact canonical Markdown emitted by the renderer."""
    try:
        document = _MarkdownParser(text).parse()
    except (IndexError, json.JSONDecodeError, TypeError, ValidationError, ValueError) as error:
        if isinstance(error, TestCaseMarkdownError):
            raise
        raise TestCaseMarkdownError(str(error).splitlines()[0]) from error
    if render_testcases_markdown(document) != text:
        raise TestCaseMarkdownError("testcase Markdown is not canonical")
    return document


class _MarkdownParser:
    def __init__(self, text: str) -> None:
        self.text = text
        self.lines = text.splitlines()
        self.index = 0

    def parse(self) -> TestCaseDocument:
        self._expect("---")
        status_match = self._match(r"status: (draft|approved|stale)")
        count_match = self._match(r"case_count: ([0-9]+)")
        self._expect("---")
        self._expect("# Test Cases")
        cases: list[TestCase] = []
        while self.index < len(self.lines):
            self._expect("")
            cases.append(self._case())
        expected_count = int(count_match.group(1))
        if expected_count != len(cases):
            raise TestCaseMarkdownError("case_count does not match parsed cases")
        return TestCaseDocument(
            status=ApprovalStatus(status_match.group(1)),
            cases=cases,
        )

    def _case(self) -> TestCase:
        heading = self._match(r"## (TC-[0-9]{3,}): (.*)")
        self._expect("")
        outline = self._prefixed("- Requirement traceability: via ")
        coverage = self._list(self._prefixed("- Coverage: "))
        priority = cast(
            Literal["high", "medium", "low"],
            self._prefixed("- Priority: "),
        )
        tags = self._list(self._prefixed("- Tags: "))
        self._expect("")
        self._expect("### Preconditions")
        self._expect("")
        preconditions = self._numbered()
        self._expect("")
        self._expect("### Test Data")
        self._expect("")
        test_data = self._numbered()
        self._expect("")
        self._expect("### Steps")
        self._expect("")
        self._expect("| Step | Action | Expected Result |")
        self._expect("| ---: | --- | --- |")
        steps: list[TestStep] = []
        while self.index < len(self.lines) and self.lines[self.index].startswith("| "):
            number = len(steps) + 1
            row = self._match(rf"\| {number} \| (.*) \| (.*) \|")
            steps.append(
                TestStep(action=_decode_text(row.group(1)), expected=_decode_text(row.group(2)))
            )
        return TestCase(
            id=heading.group(1),
            title=_decode_text(heading.group(2)),
            outline_id=_decode_text(outline),
            coverage_ids=coverage,
            preconditions=preconditions,
            test_data=test_data,
            steps=steps,
            priority=priority,
            tags=tags,
        )

    def _numbered(self) -> list[str]:
        if self.lines[self.index] == "None.":
            self.index += 1
            return []
        values: list[str] = []
        while self.index < len(self.lines):
            match = re.fullmatch(rf"{len(values) + 1}\. (.*)", self.lines[self.index])
            if match is None:
                break
            values.append(_decode_text(match.group(1)))
            self.index += 1
        if not values:
            raise TestCaseMarkdownError("expected canonical numbered values")
        return values

    def _list(self, payload: str) -> list[str]:
        parsed = json.loads(html.unescape(payload))
        if not isinstance(parsed, list) or not all(isinstance(value, str) for value in parsed):
            raise TestCaseMarkdownError("expected a JSON string array")
        return [_unescape_markdown(value) for value in parsed]

    def _prefixed(self, prefix: str) -> str:
        line = self.lines[self.index]
        if not line.startswith(prefix):
            raise TestCaseMarkdownError(f"expected {prefix.strip()}")
        self.index += 1
        return line[len(prefix) :]

    def _expect(self, expected: str) -> None:
        if self.lines[self.index] != expected:
            raise TestCaseMarkdownError(f"expected canonical line: {expected}")
        self.index += 1

    def _match(self, pattern: str) -> re.Match[str]:
        match = re.fullmatch(pattern, self.lines[self.index])
        if match is None:
            raise TestCaseMarkdownError(f"line does not match canonical form: {pattern}")
        self.index += 1
        return match


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


def _render_list(values: list[str]) -> str:
    encoded = json.dumps(
        [_escape_markdown(value) for value in values],
        ensure_ascii=False,
        separators=(", ", ": "),
    )
    return html.escape(encoded, quote=True)


def _markdown_text(value: object) -> str:
    return html.escape(_escape_markdown(str(value)), quote=True)


def _escape_markdown(value: str) -> str:
    escaped: list[str] = []
    for character in value:
        if character == "\\":
            escaped.append("\\\\")
        elif character == "\n":
            escaped.append("\\n")
        elif character == "\r":
            escaped.append("\\r")
        elif character in _MARKDOWN_PUNCTUATION:
            escaped.append(f"\\{character}")
        else:
            escaped.append(character)
    return "".join(escaped)


def _decode_text(value: str) -> str:
    return _unescape_markdown(html.unescape(value))


def _unescape_markdown(value: str) -> str:
    decoded: list[str] = []
    index = 0
    while index < len(value):
        character = value[index]
        if character != "\\":
            decoded.append(character)
            index += 1
            continue
        if index + 1 >= len(value):
            raise TestCaseMarkdownError("dangling Markdown escape")
        escaped = value[index + 1]
        decoded.append("\n" if escaped == "n" else "\r" if escaped == "r" else escaped)
        index += 2
    return "".join(decoded)
