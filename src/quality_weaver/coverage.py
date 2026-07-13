from collections import Counter
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass

from quality_weaver.catalog import Catalog
from quality_weaver.models import (
    CoverageDecision,
    CoverageLedger,
    TestOutline,
)


@dataclass(frozen=True)
class CoverageFinding:
    """One deterministic validation result tied to a coverage artifact."""

    code: str
    message: str
    artifact_id: str
    blocking: bool = True


def validate_ledger(
    ledger: CoverageLedger,
    *,
    known_requirement_ids: set[str] | frozenset[str] | None = None,
    known_target_ids: Mapping[str, AbstractSet[str]] | None = None,
    catalog: Catalog | None = None,
) -> list[CoverageFinding]:
    """Validate a ledger using only the explicitly supplied lookup inputs."""
    findings: list[CoverageFinding] = []
    key_counts = Counter(item.logical_key for item in ledger.items)
    viewpoint_ids = {viewpoint.id for viewpoint in catalog.viewpoints} if catalog else None

    if catalog is not None and ledger.catalog_version != catalog.version:
        findings.append(
            CoverageFinding(
                code="COVERAGE_CATALOG_VERSION_MISMATCH",
                message=(
                    f"Ledger catalog version {ledger.catalog_version} does not match "
                    f"catalog version {catalog.version}"
                ),
                artifact_id=ledger.catalog_version,
            )
        )

    duplicate_keys_reported: set[tuple[str, str, str, str]] = set()
    for item in ledger.items:
        if key_counts[item.logical_key] > 1 and item.logical_key not in duplicate_keys_reported:
            duplicate_keys_reported.add(item.logical_key)
            findings.append(
                CoverageFinding(
                    code="COVERAGE_DUPLICATE_KEY",
                    message="Coverage logical key is duplicated",
                    artifact_id=item.id,
                )
            )
        if known_requirement_ids is not None and item.requirement_id not in known_requirement_ids:
            findings.append(
                CoverageFinding(
                    code="COVERAGE_UNKNOWN_REQUIREMENT",
                    message=f"Unknown requirement ID: {item.requirement_id}",
                    artifact_id=item.id,
                )
            )
        if known_target_ids is not None and item.target_id not in known_target_ids.get(
            item.requirement_id, frozenset()
        ):
            findings.append(
                CoverageFinding(
                    code="COVERAGE_UNKNOWN_TARGET",
                    message=f"Unknown target ID: {item.target_id}",
                    artifact_id=item.id,
                )
            )
        if viewpoint_ids is not None and item.viewpoint_id not in viewpoint_ids:
            findings.append(
                CoverageFinding(
                    code="COVERAGE_UNKNOWN_VIEWPOINT",
                    message=f"Unknown viewpoint ID: {item.viewpoint_id}",
                    artifact_id=item.id,
                )
            )
        if not item.evidence.strip():
            findings.append(
                CoverageFinding(
                    code="COVERAGE_EVIDENCE_REQUIRED",
                    message="Coverage evidence is required",
                    artifact_id=item.id,
                )
            )
        if item.decision is CoverageDecision.NEEDS_CLARIFICATION:
            finding = (
                CoverageFinding(
                    code="COVERAGE_QUESTION_REQUIRED",
                    message="Clarification coverage requires a question ID",
                    artifact_id=item.id,
                )
                if not item.question_id
                else CoverageFinding(
                    code="COVERAGE_UNRESOLVED",
                    message="Coverage remains unresolved pending clarification",
                    artifact_id=item.id,
                )
            )
            findings.append(finding)

    return _sorted(findings)


def validate_outline_consumption(
    ledger: CoverageLedger,
    outline: TestOutline,
) -> list[CoverageFinding]:
    """Require each included coverage ID to be consumed by exactly one outline item."""
    consumption = Counter(
        coverage_id for outline_item in outline.items for coverage_id in outline_item.coverage_ids
    )
    findings: list[CoverageFinding] = []
    for item in ledger.items:
        if item.decision is not CoverageDecision.INCLUDE:
            continue
        count = consumption[item.id]
        if count == 0:
            findings.append(
                CoverageFinding(
                    code="COVERAGE_NOT_CONSUMED",
                    message="Included coverage is not consumed by the outline",
                    artifact_id=item.id,
                )
            )
        elif count > 1:
            findings.append(
                CoverageFinding(
                    code="COVERAGE_CONSUMED_TWICE",
                    message=f"Included coverage is consumed {count} times",
                    artifact_id=item.id,
                )
            )
    return _sorted(findings)


def _sorted(findings: list[CoverageFinding]) -> list[CoverageFinding]:
    return sorted(findings, key=lambda item: (item.code, item.artifact_id, item.message))
