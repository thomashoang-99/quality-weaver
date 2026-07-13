import json
from pathlib import Path

import pytest

from quality_weaver.schema import write_schemas

SCHEMA_NAMES = (
    "requirement.schema.json",
    "coverage-ledger.schema.json",
    "test-outline.schema.json",
    "testcase.schema.json",
)


@pytest.mark.parametrize("schema_name", SCHEMA_NAMES)
def test_committed_schema_matches_generated_schema(tmp_path: Path, schema_name: str) -> None:
    write_schemas(tmp_path)

    generated = (tmp_path / schema_name).read_bytes()
    committed = (Path("schemas") / schema_name).read_bytes()

    assert generated == committed
    assert generated.endswith(b"\n")
    assert generated.decode("utf-8") == json.dumps(
        json.loads(generated), indent=2, sort_keys=True
    ) + "\n"
