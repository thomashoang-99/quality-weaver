from pathlib import Path

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from quality_weaver.catalog import Catalog
from quality_weaver.cli import app
from quality_weaver.models import CoverageDecision, CoverageItem, CoverageLedger
from quality_weaver.testmap import render_testmap

CATALOG = Catalog.load(Path("viewpoints"))
CATALOG_PATH = Path("viewpoints").resolve()
CLI_CONTEXT = [
    "--catalog",
    str(CATALOG_PATH),
    "--requirement-id",
    "REQ-ALPHA",
    "--requirement-id",
    "REQ-BETA",
    "--target",
    "REQ-ALPHA=TARGET-COV-001",
    "--target",
    "REQ-ALPHA=TARGET-COV-002",
    "--target",
    "REQ-BETA=TARGET-COV-003",
]


def item(
    coverage_id: str,
    requirement_id: str,
    viewpoint_id: str,
    decision: CoverageDecision,
    priority: str,
) -> CoverageItem:
    return CoverageItem(
        id=coverage_id,
        requirement_id=requirement_id,
        target_id=f"TARGET-{coverage_id}",
        viewpoint_id=viewpoint_id,
        condition="default",
        decision=decision,
        priority=priority,  # type: ignore[arg-type]
        evidence=f"Evidence for {coverage_id}",
        rationale=f"Rationale for {coverage_id}",
        question_id="Q-002" if decision is CoverageDecision.NEEDS_CLARIFICATION else None,
    )


def sample_ledger() -> CoverageLedger:
    return CoverageLedger(
        catalog_version=CATALOG.version,
        items=[
            item(
                "COV-003",
                "REQ-BETA",
                "VP-NAVIGATION-001",
                CoverageDecision.EXCLUDE,
                "low",
            ),
            item(
                "COV-002",
                "REQ-ALPHA",
                "VP-INPUT-VALIDATION-002",
                CoverageDecision.NEEDS_CLARIFICATION,
                "medium",
            ),
            item(
                "COV-001",
                "REQ-ALPHA",
                "VP-INPUT-VALIDATION-001",
                CoverageDecision.INCLUDE,
                "high",
            ),
        ],
    )


def test_testmap_has_fixed_columns_sorted_rows_and_ledger_counts() -> None:
    markdown = render_testmap(sample_ledger(), CATALOG)

    header = (
        "| Unit | Applicable | Included | Excluded | Questions | High | Medium | Low | Status |"
    )
    assert header in markdown
    alpha = "| REQ-ALPHA | 2 | 1 | 0 | 1 | 1 | 1 | 0 | blocked |"
    beta = "| REQ-BETA | 1 | 0 | 1 | 0 | 0 | 0 | 1 | ready |"
    assert alpha in markdown
    assert beta in markdown
    assert markdown.index(alpha) < markdown.index(beta)


def test_viewpoint_groups_and_coverage_references_are_sorted() -> None:
    markdown = render_testmap(sample_ledger(), CATALOG)

    assert markdown.index("| input-validation |") < markdown.index("| navigation |")
    assert "COV-001, COV-002" in markdown
    assert "COV-003" in markdown


def test_testmap_does_not_invent_counts_levels_or_rationales() -> None:
    markdown = render_testmap(sample_ledger(), CATALOG)

    assert "Rationale for" not in markdown
    assert "Critical" not in markdown
    assert "model" not in markdown.casefold()


def test_testmap_rejects_catalog_version_mismatch() -> None:
    ledger = sample_ledger().model_copy(update={"catalog_version": "0.9.0"})

    with pytest.raises(ValueError, match="catalog version"):
        render_testmap(ledger, CATALOG)


def test_anomalies_are_sorted_by_code_and_block_the_unit() -> None:
    anomalous = sample_ledger().items[1].model_copy(
        update={"evidence": "", "question_id": None}
    )
    ledger = sample_ledger().model_copy(update={"items": [anomalous]})

    markdown = render_testmap(ledger, CATALOG)

    assert markdown.index("COVERAGE_EVIDENCE_REQUIRED") < markdown.index(
        "COVERAGE_QUESTION_REQUIRED"
    )
    assert "| REQ-ALPHA | 1 | 0 | 0 | 1 | 0 | 1 | 0 | blocked |" in markdown


def test_blocking_reference_finding_blocks_otherwise_resolved_unit() -> None:
    anomalous = sample_ledger().items[0].model_copy(update={"evidence": ""})
    ledger = sample_ledger().model_copy(update={"items": [anomalous]})

    markdown = render_testmap(ledger, CATALOG)

    assert "| REQ-BETA | 1 | 0 | 1 | 0 | 0 | 0 | 1 | blocked |" in markdown


def test_cli_reports_yaml_schema_errors_without_traceback(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.yaml"
    ledger_path.write_text("items: [", encoding="utf-8")

    result = CliRunner().invoke(
        app, ["coverage", "validate", str(ledger_path), *CLI_CONTEXT]
    )

    assert result.exit_code != 0
    assert "Invalid coverage ledger:" in result.stdout
    assert "Traceback" not in result.stdout


def test_cli_reports_model_schema_errors_without_traceback(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.yaml"
    ledger_path.write_text("items: []\n", encoding="utf-8")

    result = CliRunner().invoke(
        app, ["coverage", "validate", str(ledger_path), *CLI_CONTEXT]
    )

    assert result.exit_code != 0
    assert "Invalid coverage ledger:" in result.stdout
    assert "Traceback" not in result.stdout


def test_cli_does_not_misclassify_malformed_items_as_duplicates(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.yaml"
    ledger_path.write_text("items: [{}, {}]\n", encoding="utf-8")

    result = CliRunner().invoke(
        app, ["coverage", "validate", str(ledger_path), *CLI_CONTEXT]
    )

    assert result.exit_code != 0
    assert "Invalid coverage ledger:" in result.stdout
    assert "COVERAGE_DUPLICATE_KEY" not in result.stdout


def test_cli_renders_testmap(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.yaml"
    output_path = tmp_path / "test-map.md"
    ledger_path.write_text(sample_ledger().model_dump_json(), encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "testmap",
            "render",
            str(ledger_path),
            "--out",
            str(output_path),
            *CLI_CONTEXT,
        ],
    )

    assert result.exit_code == 0
    assert output_path.read_text(encoding="utf-8").startswith("# Test Map\n")


def test_cli_explicit_catalog_does_not_depend_on_caller_cwd(
    tmp_path: Path, monkeypatch
) -> None:
    ledger_path = tmp_path / "ledger.yaml"
    output_path = tmp_path / "test-map.md"
    ledger_path.write_text(sample_ledger().model_dump_json(), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(
        app,
        [
            "testmap",
            "render",
            str(ledger_path),
            "--out",
            str(output_path),
            *CLI_CONTEXT,
        ],
    )

    assert result.exit_code == 0


def test_cli_requires_explicit_validation_context(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.yaml"
    ledger_path.write_text(sample_ledger().model_dump_json(), encoding="utf-8")

    result = CliRunner().invoke(app, ["coverage", "validate", str(ledger_path)])

    assert result.exit_code != 0
    assert "--catalog" in result.stderr
    help_result = CliRunner().invoke(app, ["coverage", "validate", "--help"])
    assert "--requirement-id" in help_result.stdout
    assert "--target" in help_result.stdout


def test_cli_translates_duplicate_key_to_coverage_finding(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.yaml"
    first = sample_ledger().items[0]
    duplicate = first.model_copy(update={"id": "COV-004"})
    raw = sample_ledger().model_dump(mode="json")
    raw["items"] = [first.model_dump(mode="json"), duplicate.model_dump(mode="json")]
    with ledger_path.open("w", encoding="utf-8") as stream:
        YAML().dump(raw, stream)

    result = CliRunner().invoke(
        app, ["coverage", "validate", str(ledger_path), *CLI_CONTEXT]
    )

    assert result.exit_code != 0
    assert "COVERAGE_DUPLICATE_KEY COV-004" in result.stdout
    assert "Traceback" not in result.stdout
