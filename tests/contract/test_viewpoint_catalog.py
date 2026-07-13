import hashlib
import os
import re
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

from quality_weaver.catalog import Catalog
from quality_weaver.legacy_inventory import parse_legacy_viewpoint_markdown
from quality_weaver.models import ViewpointScope

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CATALOG_ROOT = PROJECT_ROOT / "viewpoints"
PROVENANCE_PATH = PROJECT_ROOT / "docs" / "migration" / "viewpoint-provenance.yaml"
INVENTORY_PATH = PROJECT_ROOT / "tests" / "fixtures" / "legacy-viewpoint-inventory.yaml"
LEGACY_ROOT_ENV = "QUALITY_WEAVER_LEGACY_ROOT"
EXPECTED_FILES = {
    "local/ui-layout.yaml",
    "local/display-controls.yaml",
    "local/data-visualization.yaml",
    "local/container-structural.yaml",
    "local/input-validation.yaml",
    "local/action-controls.yaml",
    "local/advanced.yaml",
    "local/api.yaml",
    "local/keyboard-mouse.yaml",
    "cross-requirement/navigation.yaml",
    "cross-requirement/data-continuity.yaml",
    "cross-requirement/it-flow.yaml",
    "cross-requirement/e2e-journey.yaml",
    "system-wide/mobile.yaml",
    "system-wide/batch-job-cron.yaml",
}
SCOPE_DIRECTORIES = {
    "local": ViewpointScope.LOCAL,
    "cross-requirement": ViewpointScope.CROSS_REQUIREMENT,
    "system-wide": ViewpointScope.SYSTEM_WIDE,
}
SOURCE_GROUPS = {
    "01-ui.md": "ui-layout",
    "02-display-controls.md": "display-controls",
    "03-data-visualization-controls.md": "data-visualization",
    "04-navigation.md": "navigation",
    "05-container-structural-controls.md": "container-structural",
    "06-input-controls.md": "input-validation",
    "07-action-controls.md": "action-controls",
    "08-advanced.md": "advanced",
    "09-mobile-specific.md": "mobile",
    "10-batch-job-cron.md": "batch-job",
    "11-api.md": "api",
    "12-it-flow.md": "it-flow",
    "13-e2e-journey.md": "e2e-journey",
    "14-keyboard-mouse-interaction.md": "keyboard-mouse",
}
GROUP_SCOPES = {
    "ui-layout": ViewpointScope.LOCAL,
    "display-controls": ViewpointScope.LOCAL,
    "data-visualization": ViewpointScope.LOCAL,
    "container-structural": ViewpointScope.LOCAL,
    "input-validation": ViewpointScope.LOCAL,
    "action-controls": ViewpointScope.LOCAL,
    "advanced": ViewpointScope.LOCAL,
    "api": ViewpointScope.LOCAL,
    "keyboard-mouse": ViewpointScope.LOCAL,
    "navigation": ViewpointScope.CROSS_REQUIREMENT,
    "data-continuity": ViewpointScope.CROSS_REQUIREMENT,
    "it-flow": ViewpointScope.CROSS_REQUIREMENT,
    "e2e-journey": ViewpointScope.CROSS_REQUIREMENT,
    "mobile": ViewpointScope.SYSTEM_WIDE,
    "batch-job": ViewpointScope.SYSTEM_WIDE,
}


def _load_yaml(path: Path) -> Any:
    yaml = YAML(typ="safe")
    return yaml.load(path.read_text(encoding="utf-8"))


def _inventory_files() -> list[dict[str, Any]]:
    inventory = _load_yaml(INVENTORY_PATH)
    assert set(inventory) == {"schema_version", "inventory_version", "files"}
    assert inventory["schema_version"] == "quality-weaver/legacy-viewpoint-inventory/v1"
    assert inventory["inventory_version"] == "1.0.0"
    files = inventory["files"]
    assert isinstance(files, list)
    assert len(files) == 14
    assert len({source["path"] for source in files}) == len(files)
    for source in files:
        assert set(source) == {"path", "sha256", "rows"}
        assert re.fullmatch(r"rules/viewpoints/[0-9]{2}-[^/]+\.md", source["path"])
        assert re.fullmatch(r"[a-f0-9]{64}", source["sha256"])
        assert isinstance(source["rows"], list)
        assert source["rows"]
        for row in source["rows"]:
            assert set(row) == {
                "source_row_id",
                "path",
                "heading",
                "aspect",
                "viewpoint",
                "expected_result",
            }
            assert row["path"] == source["path"]
            assert row["source_row_id"] == (
                f"{row['path']}::{row['heading']}::{row['aspect']}"
            )
    return files


def _inventory_rows() -> dict[str, dict[str, str]]:
    all_rows = [row for source in _inventory_files() for row in source["rows"]]
    rows = {row["source_row_id"]: row for row in all_rows}
    assert len(all_rows) == 412
    assert len(rows) == 412
    return rows


def _source_group(source: dict[str, str]) -> str:
    if (
        source["path"].endswith("01-ui.md")
        and source["aspect"] == "Data carried from previous screen"
    ):
        return "data-continuity"
    return SOURCE_GROUPS[Path(source["path"]).name]


def test_frozen_inventory_has_exact_provenance_coverage() -> None:
    inventory_rows = _inventory_rows()
    records = _load_yaml(PROVENANCE_PATH)["rows"]
    records_by_identity = {record["source_row_id"]: record for record in records}

    assert len(records_by_identity) == len(records)
    assert set(records_by_identity) == set(inventory_rows)
    for identity, source in inventory_rows.items():
        record = records_by_identity[identity]
        assert record["source"] == {
            "path": source["path"],
            "heading": source["heading"],
            "aspect": source["aspect"],
            "viewpoint": source["viewpoint"],
            "expected_result": source["expected_result"],
        }
        assert ("migrated_id" in record) != ("deduplicated_to" in record)


def test_catalog_exactly_matches_migrated_targets_and_source_semantics() -> None:
    catalog = Catalog.load(CATALOG_ROOT)
    catalog_ids = {viewpoint.id for viewpoint in catalog.viewpoints}
    inventory_rows = _inventory_rows()
    records = _load_yaml(PROVENANCE_PATH)["rows"]
    migrated_records = [record for record in records if "migrated_id" in record]
    migrated_ids = [record["migrated_id"] for record in migrated_records]
    deduplication_targets = {
        record["deduplicated_to"] for record in records if "deduplicated_to" in record
    }

    assert len(migrated_ids) == len(set(migrated_ids))
    assert catalog_ids == set(migrated_ids)
    assert deduplication_targets <= set(migrated_ids)
    for record in migrated_records:
        source = inventory_rows[record["source_row_id"]]
        target = catalog.get(record["migrated_id"])
        expected_group = _source_group(source)
        assert target.name == source["aspect"]
        assert target.signals == [source["heading"], source["aspect"]]
        assert target.guidance == (
            f"{source['viewpoint']} Expected: {source['expected_result']}"
        )
        assert target.group == expected_group
        assert target.scope == GROUP_SCOPES[expected_group]


def test_all_viewpoint_ids_are_unique() -> None:
    catalog = Catalog.load(CATALOG_ROOT)
    ids = [viewpoint.id for viewpoint in catalog.viewpoints]

    assert len(ids) == len(set(ids))


def test_catalog_uses_only_declared_files_in_the_correct_scope() -> None:
    catalog_document = _load_yaml(CATALOG_ROOT / "catalog.yaml")
    declared_files = {group["file"] for group in catalog_document["groups"]}
    actual_files = {
        path.relative_to(CATALOG_ROOT).as_posix() for path in CATALOG_ROOT.glob("*/*.yaml")
    }

    assert catalog_document["version"] == "1.0.0"
    assert declared_files == EXPECTED_FILES
    assert actual_files == EXPECTED_FILES
    for relative_path in EXPECTED_FILES:
        expected_scope = SCOPE_DIRECTORIES[Path(relative_path).parts[0]]
        document = _load_yaml(CATALOG_ROOT / relative_path)
        assert isinstance(document, list)
        assert document
        assert all(row["scope"] == expected_scope.value for row in document)


def test_catalog_is_loadable_and_contains_required_migration_topics() -> None:
    catalog = Catalog.load(CATALOG_ROOT)
    searchable = "\n".join(
        f"{viewpoint.name} {viewpoint.guidance}".lower() for viewpoint in catalog.viewpoints
    )

    assert catalog.viewpoints
    for phrase in (
        "required",
        "empty",
        "boundary",
        "double click",
        "initial display",
        "back",
        "data carried",
        "interruption",
        "orientation",
        "permission",
        "deep link",
    ):
        assert phrase in searchable


def test_live_legacy_inventory_matches_frozen_fixture_without_writes() -> None:
    configured_root = os.environ.get(LEGACY_ROOT_ENV)
    if configured_root is None:
        pytest.skip(f"set {LEGACY_ROOT_ENV} to run the live legacy migration audit")
    legacy_root = Path(configured_root)
    assert legacy_root.is_dir()
    inventory_files = _inventory_files()
    expected_names = {Path(source["path"]).name for source in inventory_files}
    actual_paths = sorted(legacy_root.glob("[0-9][0-9]-*.md"))
    assert {path.name for path in actual_paths} == expected_names
    original_bytes = {path.name: path.read_bytes() for path in actual_paths}

    for source in inventory_files:
        path = legacy_root / Path(source["path"]).name
        content = original_bytes[path.name]
        assert hashlib.sha256(content).hexdigest() == source["sha256"]
        parsed = parse_legacy_viewpoint_markdown(content.decode("utf-8"), source["path"])
        assert [
            {
                "source_row_id": row.source_row_id,
                "path": row.path,
                "heading": row.heading,
                "aspect": row.aspect,
                "viewpoint": row.viewpoint,
                "expected_result": row.expected_result,
            }
            for row in parsed
        ] == source["rows"]

    assert {path.name: path.read_bytes() for path in actual_paths} == original_bytes
