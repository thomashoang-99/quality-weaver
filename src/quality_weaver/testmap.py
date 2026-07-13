from collections import defaultdict
from collections.abc import Mapping
from collections.abc import Set as AbstractSet

from quality_weaver.catalog import Catalog
from quality_weaver.coverage import CoverageFinding, validate_ledger
from quality_weaver.models import CoverageDecision, CoverageItem, CoverageLedger

_DECISION_COLUMN = {
    CoverageDecision.INCLUDE: "Included",
    CoverageDecision.EXCLUDE: "Excluded",
    CoverageDecision.NEEDS_CLARIFICATION: "Questions",
}


def render_testmap(
    ledger: CoverageLedger,
    catalog: Catalog,
    *,
    known_requirement_ids: set[str] | frozenset[str] | None = None,
    known_target_ids: Mapping[str, AbstractSet[str]] | None = None,
) -> str:
    """Render a deterministic Markdown projection of a typed coverage ledger."""
    findings = validate_ledger(
        ledger,
        known_requirement_ids=known_requirement_ids,
        known_target_ids=known_target_ids,
        catalog=catalog,
    )
    version_mismatch = next(
        (
            finding
            for finding in findings
            if finding.code == "COVERAGE_CATALOG_VERSION_MISMATCH"
        ),
        None,
    )
    if version_mismatch is not None:
        raise ValueError(version_mismatch.message)
    by_unit: dict[str, list[CoverageItem]] = defaultdict(list)
    for item in ledger.items:
        by_unit[item.requirement_id].append(item)
    blocked_artifact_ids = {
        finding.artifact_id for finding in findings if finding.blocking
    }

    lines = [
        "# Test Map",
        "",
        "## Coverage Summary",
        "",
        "| Unit | Applicable | Included | Excluded | Questions | High | Medium | Low | Status |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for unit in sorted(by_unit):
        items = by_unit[unit]
        decision_counts = _decision_counts(items)
        priority_counts = _priority_counts(items)
        status = (
            "blocked"
            if any(
                item.decision is CoverageDecision.NEEDS_CLARIFICATION
                or item.id in blocked_artifact_ids
                for item in items
            )
            else "ready"
        )
        lines.append(
            f"| {unit} | {len(items)} | {decision_counts['Included']} | "
            f"{decision_counts['Excluded']} | {decision_counts['Questions']} | "
            f"{priority_counts['high']} | {priority_counts['medium']} | "
            f"{priority_counts['low']} | {status} |"
        )

    lines.extend(
        [
            "",
            "## Viewpoint Group Matrix",
            "",
            "| Viewpoint Group | Unit | Applicable | Included | Excluded | Questions | "
            "Coverage IDs |",
            "| --- | --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    group_units: dict[tuple[str, str], list[CoverageItem]] = defaultdict(list)
    for item in ledger.items:
        group = _viewpoint_group(catalog, item.viewpoint_id)
        group_units[(group, item.requirement_id)].append(item)
    for (group, unit), items in sorted(group_units.items()):
        counts = _decision_counts(items)
        coverage_ids = ", ".join(sorted(item.id for item in items))
        lines.append(
            f"| {group} | {unit} | {len(items)} | {counts['Included']} | "
            f"{counts['Excluded']} | {counts['Questions']} | {coverage_ids} |"
        )

    lines.extend(["", "## Anomalies", ""])
    if findings:
        lines.extend(_finding_line(finding) for finding in findings)
    else:
        lines.append("None.")
    return "\n".join(lines) + "\n"


def _decision_counts(items: list[CoverageItem]) -> dict[str, int]:
    counts = {"Included": 0, "Excluded": 0, "Questions": 0}
    for item in items:
        counts[_DECISION_COLUMN[item.decision]] += 1
    return counts


def _priority_counts(items: list[CoverageItem]) -> dict[str, int]:
    counts = {"high": 0, "medium": 0, "low": 0}
    for item in items:
        counts[item.priority] += 1
    return counts


def _viewpoint_group(catalog: Catalog, viewpoint_id: str) -> str:
    try:
        return catalog.get(viewpoint_id).group
    except KeyError:
        return "unknown"


def _finding_line(finding: CoverageFinding) -> str:
    return f"- `{finding.code}` ({finding.artifact_id}): {finding.message}"
