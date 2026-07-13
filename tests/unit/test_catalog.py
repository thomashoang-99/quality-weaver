from pathlib import Path

import pytest
from ruamel.yaml import YAML

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


def test_duplicate_group_names_use_routing_normalization(tmp_path: Path) -> None:
    yaml = YAML()
    viewpoint = {
        "id": "VP-GROUP-001",
        "name": "Example",
        "group": "Example",
        "scope": "local",
        "applies_to": [],
        "signals": [],
        "exclusions": [],
        "clarification_prompts": [],
        "default_priority": "low",
        "guidance": "Example guidance",
    }
    with (tmp_path / "example.yaml").open("w", encoding="utf-8") as stream:
        yaml.dump([viewpoint], stream)
    with (tmp_path / "catalog.yaml").open("w", encoding="utf-8") as stream:
        yaml.dump(
            {
                "version": "1.0.0",
                "groups": [
                    {"name": "Example", "file": "example.yaml"},
                    {"name": "EXAMPLE", "file": "example.yaml"},
                ],
            },
            stream,
        )

    with pytest.raises(ValueError, match="duplicate catalog group"):
        Catalog.load(tmp_path)
