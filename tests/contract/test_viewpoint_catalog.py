import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from quality_weaver.catalog import Catalog
from quality_weaver.models import ViewpointScope

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CATALOG_ROOT = PROJECT_ROOT / "viewpoints"
PROVENANCE_PATH = PROJECT_ROOT / "docs" / "migration" / "viewpoint-provenance.yaml"
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


@dataclass(frozen=True)
class LegacyRow:
    source_row_id: str
    path: str
    heading: str
    aspect: str
    viewpoint: str
    expected_result: str


def _legacy_root() -> Path:
    for ancestor in PROJECT_ROOT.parents:
        candidate = ancestor / "qa-engine" / "qc-testcase" / "rules" / "viewpoints"
        if candidate.is_dir():
            return candidate
    raise AssertionError("legacy qa-engine viewpoint directory is unavailable")


def _table_cells(line: str) -> list[str]:
    return [cell.strip().replace(r"\|", "|") for cell in re.split(r"(?<!\\)\|", line)[1:-1]]


def _legacy_rows() -> dict[str, LegacyRow]:
    rows: dict[str, LegacyRow] = {}
    files = sorted(_legacy_root().glob("[0-9][0-9]-*.md"))
    assert len(files) == 14
    for source in files:
        heading = ""
        for line in source.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                heading = line.removeprefix("## ").strip()
            if not line.startswith("|"):
                continue
            cells = _table_cells(line)
            if len(cells) != 3 or cells[0] == "Aspect" or set(cells[0]) <= {"-", ":"}:
                continue
            relative_path = f"rules/viewpoints/{source.name}"
            identity = f"{relative_path}::{heading}::{cells[0]}"
            assert identity not in rows
            rows[identity] = LegacyRow(identity, relative_path, heading, *cells)
    return rows


def _load_yaml(path: Path) -> Any:
    yaml = YAML(typ="safe")
    return yaml.load(path.read_text(encoding="utf-8"))


def test_every_legacy_row_has_exact_provenance_coverage() -> None:
    legacy_rows = _legacy_rows()
    provenance = _load_yaml(PROVENANCE_PATH)
    records = provenance["rows"]
    records_by_identity = {record["source_row_id"]: record for record in records}

    assert len(records_by_identity) == len(records)
    assert set(records_by_identity) == set(legacy_rows)
    for identity, legacy in legacy_rows.items():
        record = records_by_identity[identity]
        assert record["source"] == {
            "path": legacy.path,
            "heading": legacy.heading,
            "aspect": legacy.aspect,
            "viewpoint": legacy.viewpoint,
            "expected_result": legacy.expected_result,
        }
        assert ("migrated_id" in record) != ("deduplicated_to" in record)


def test_provenance_targets_are_valid_and_migrations_are_unique() -> None:
    catalog = Catalog.load(CATALOG_ROOT)
    ids = {viewpoint.id for viewpoint in catalog.viewpoints}
    records = _load_yaml(PROVENANCE_PATH)["rows"]
    migrated_ids = [record["migrated_id"] for record in records if "migrated_id" in record]
    targets = {
        record.get("migrated_id", record.get("deduplicated_to")) for record in records
    }

    assert len(migrated_ids) == len(set(migrated_ids))
    assert targets <= ids


def test_all_viewpoint_ids_are_unique() -> None:
    catalog = Catalog.load(CATALOG_ROOT)
    ids = [viewpoint.id for viewpoint in catalog.viewpoints]

    assert len(ids) == len(set(ids))


def test_catalog_uses_only_declared_files_in_the_correct_scope() -> None:
    catalog_document = _load_yaml(CATALOG_ROOT / "catalog.yaml")
    declared_files = {group["file"] for group in catalog_document["groups"]}
    actual_files = {
        path.relative_to(CATALOG_ROOT).as_posix()
        for path in CATALOG_ROOT.glob("*/*.yaml")
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
