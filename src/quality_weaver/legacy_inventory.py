import re
from dataclasses import dataclass

_EXPECTED_HEADER = ("Aspect", "Test Viewpoint", "Expected Result")
_HEADING = re.compile(r"^\s*##\s+(.+?)\s*$")
_SEPARATOR = re.compile(r"^:?-{3,}:?$")


class LegacyFormatError(ValueError):
    """Raised when a legacy viewpoint table does not match the migration contract."""


@dataclass(frozen=True)
class LegacySourceRow:
    source_row_id: str
    path: str
    heading: str
    aspect: str
    viewpoint: str
    expected_result: str


def parse_legacy_viewpoint_markdown(text: str, relative_path: str) -> tuple[LegacySourceRow, ...]:
    """Strictly parse all three-column viewpoint tables in one legacy Markdown document."""
    lines = text.splitlines()
    rows: list[LegacySourceRow] = []
    identities: set[str] = set()
    heading = ""
    index = 0
    while index < len(lines):
        line = lines[index]
        heading_match = _HEADING.fullmatch(line)
        if heading_match:
            heading = heading_match.group(1)
            index += 1
            continue
        if "|" in line and not line.lstrip().startswith("|"):
            raise LegacyFormatError(f"unsupported table syntax at line {index + 1}")
        if not line.lstrip().startswith("|"):
            index += 1
            continue
        header = _table_cells(line, index + 1)
        if tuple(header) != _EXPECTED_HEADER:
            raise LegacyFormatError(
                f"unexpected table header at line {index + 1}: expected {_EXPECTED_HEADER!r}"
            )
        if index + 1 >= len(lines) or not lines[index + 1].lstrip().startswith("|"):
            raise LegacyFormatError(f"missing table separator after line {index + 1}")
        separator = _table_cells(lines[index + 1], index + 2)
        if len(separator) != 3 or any(not _SEPARATOR.fullmatch(cell) for cell in separator):
            raise LegacyFormatError(f"invalid table separator at line {index + 2}")

        index += 2
        data_rows = 0
        while index < len(lines) and lines[index].lstrip().startswith("|"):
            cells = _table_cells(lines[index], index + 1)
            if len(cells) != 3:
                raise LegacyFormatError(
                    f"expected 3 cells at line {index + 1}, found {len(cells)}"
                )
            if any(not cell for cell in cells):
                raise LegacyFormatError(f"empty table cell at line {index + 1}")
            aspect, viewpoint, expected_result = cells
            identity = f"{relative_path}::{heading}::{aspect}"
            if identity in identities:
                raise LegacyFormatError(f"duplicate source row identity: {identity}")
            identities.add(identity)
            rows.append(
                LegacySourceRow(
                    source_row_id=identity,
                    path=relative_path,
                    heading=heading,
                    aspect=aspect,
                    viewpoint=viewpoint,
                    expected_result=expected_result,
                )
            )
            data_rows += 1
            index += 1
        if index < len(lines) and lines[index].strip() and "|" in lines[index]:
            raise LegacyFormatError(f"malformed table row at line {index + 1}")
        if data_rows == 0:
            raise LegacyFormatError(f"table has no data rows after line {index}")
    return tuple(rows)


def _table_cells(line: str, line_number: int) -> list[str]:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        raise LegacyFormatError(f"malformed table row at line {line_number}")

    cells: list[str] = []
    current: list[str] = []
    body = stripped[1:-1]
    index = 0
    while index < len(body):
        character = body[index]
        if character == "\\" and index + 1 < len(body) and body[index + 1] == "|":
            current.append("|")
            index += 2
            continue
        if character == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(character)
        index += 1
    cells.append("".join(current).strip())
    return cells
