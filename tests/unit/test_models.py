import pytest
from pydantic import ValidationError

from quality_weaver.models import CoverageDecision, CoverageItem, CoverageLedger


def test_coverage_logical_key_must_be_unique() -> None:
    item = CoverageItem(
        id="COV-001",
        requirement_id="REQ-001",
        target_id="CTRL-EMAIL",
        viewpoint_id="VP-INPUT-REQUIRED",
        condition="empty",
        decision=CoverageDecision.INCLUDE,
        priority="high",
        evidence="Email is required",
        rationale="Required input",
    )

    with pytest.raises(ValidationError, match="duplicate coverage logical key"):
        CoverageLedger(
            catalog_version="1.0.0",
            items=[item, item.model_copy(update={"id": "COV-002"})],
        )
