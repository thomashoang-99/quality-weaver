from pathlib import Path

import pytest

from quality_weaver.catalog import Catalog


def test_textbox_routes_only_relevant_groups() -> None:
    catalog = Catalog.load(Path("viewpoints"))

    groups = catalog.route(entity_types={"textbox"}, risks=set(), enabled_groups=set())

    assert "input-validation" in groups
    assert "batch-job" not in groups


def test_enabled_group_is_routed_explicitly() -> None:
    catalog = Catalog.load(Path("viewpoints"))

    groups = catalog.route(entity_types=set(), risks=set(), enabled_groups={"BATCH-JOB"})

    assert groups == {"batch-job"}


def test_get_returns_a_viewpoint_by_stable_id() -> None:
    catalog = Catalog.load(Path("viewpoints"))

    viewpoint = catalog.get("VP-INPUT-VALIDATION-001")

    assert viewpoint.id == "VP-INPUT-VALIDATION-001"


def test_get_rejects_an_unknown_viewpoint() -> None:
    catalog = Catalog.load(Path("viewpoints"))

    with pytest.raises(KeyError, match="unknown viewpoint"):
        catalog.get("VP-NOT-THERE")


def test_returned_viewpoint_cannot_mutate_catalog_state() -> None:
    catalog = Catalog.load(Path("viewpoints"))
    viewpoint = catalog.get("VP-INPUT-VALIDATION-001")

    viewpoint.id = "VP-CALLER-MUTATION"

    assert catalog.get("VP-INPUT-VALIDATION-001").id == "VP-INPUT-VALIDATION-001"
    with pytest.raises(KeyError, match="unknown viewpoint"):
        catalog.get("VP-CALLER-MUTATION")
