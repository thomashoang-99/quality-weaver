import pytest

from quality_weaver.legacy_inventory import LegacyFormatError, parse_legacy_viewpoint_markdown


def test_parser_supports_indented_headings_and_tables() -> None:
    document = """
  ## Input Rules

  | Aspect | Test Viewpoint | Expected Result |
  | :--- | ---: | :---: |
  | Required | Submit an empty value | A required error is displayed |
"""

    rows = parse_legacy_viewpoint_markdown(document, "rules/viewpoints/06-input-controls.md")

    assert len(rows) == 1
    assert rows[0].source_row_id == (
        "rules/viewpoints/06-input-controls.md::Input Rules::Required"
    )
    assert rows[0].viewpoint == "Submit an empty value"


def test_parser_supports_a_document_level_table() -> None:
    document = """
# Keyboard
| Aspect | Test Viewpoint | Expected Result |
|---|---|---|
| Tab order | Press TAB | Focus advances |
"""

    rows = parse_legacy_viewpoint_markdown(
        document, "rules/viewpoints/14-keyboard-mouse-interaction.md"
    )

    assert rows[0].heading == ""
    assert rows[0].source_row_id.endswith("::::Tab order")


def test_parser_preserves_an_escaped_pipe_inside_a_cell() -> None:
    document = r"""
## Input
| Aspect | Test Viewpoint | Expected Result |
|---|---|---|
| A \| B | Exercise both | Both work |
"""

    rows = parse_legacy_viewpoint_markdown(document, "rules/viewpoints/example.md")

    assert rows[0].aspect == "A | B"


@pytest.mark.parametrize(
    ("document", "message"),
    [
        (
            "## Input\n| Wrong | Test Viewpoint | Expected Result |\n|---|---|---|\n| A | B | C |",
            "unexpected table header",
        ),
        (
            "## Input\n"
            "| Aspect | Test Viewpoint | Expected Result |\n"
            "|---|nope|---|\n"
            "| A | B | C |",
            "invalid table separator",
        ),
        (
            "## Input\n"
            "| Aspect | Test Viewpoint | Expected Result |\n"
            "|---|---|---|\n"
            "| A | B | C | D |",
            "expected 3 cells",
        ),
        (
            "## Input\n| Aspect | Test Viewpoint | Expected Result |\n|---|---|---|\n| A | B |",
            "expected 3 cells",
        ),
        (
            "## Input\n"
            "| Aspect | Test Viewpoint | Expected Result |\n"
            "|---|---|---|\n"
            "| A | B | C |\n"
            "D | E | F |",
            "malformed table row",
        ),
        (
            "## Input\n"
            "Aspect | Test Viewpoint | Expected Result\n"
            "---|---|---\n"
            "A | B | C",
            "unsupported table syntax",
        ),
        (
            "## Input\n"
            "| Aspect | Test Viewpoint | Expected Result |\n"
            "|---|---|---|\n"
            "| A | B | C |\n"
            "\n"
            "D | E | F |",
            "unsupported table syntax",
        ),
    ],
)
def test_parser_rejects_malformed_tables(document: str, message: str) -> None:
    with pytest.raises(LegacyFormatError, match=message):
        parse_legacy_viewpoint_markdown(document, "rules/viewpoints/example.md")


def test_parser_rejects_duplicate_source_row_identity() -> None:
    document = """
## Input
| Aspect | Test Viewpoint | Expected Result |
|---|---|---|
| Required | First | First result |
| Required | Second | Second result |
"""

    with pytest.raises(LegacyFormatError, match="duplicate source row identity"):
        parse_legacy_viewpoint_markdown(document, "rules/viewpoints/example.md")
