import argparse
import json
from pathlib import Path

from pydantic import BaseModel

from quality_weaver.models import (
    CoverageLedger,
    RequirementDocument,
    TestCaseDocument,
    TestOutline,
)

SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "requirement.schema.json": RequirementDocument,
    "coverage-ledger.schema.json": CoverageLedger,
    "test-outline.schema.json": TestOutline,
    "testcase.schema.json": TestCaseDocument,
}


def write_schemas(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, model in SCHEMA_MODELS.items():
        schema = json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n"
        (output_dir / filename).write_text(schema, encoding="utf-8", newline="")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate QualityWeaver JSON Schemas.")
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    write_schemas(args.output_dir)


if __name__ == "__main__":
    main()
