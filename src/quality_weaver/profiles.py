import re
from enum import StrEnum
from pathlib import Path
from string import Formatter
from typing import Any, Literal, Self

from pydantic import Field, PrivateAttr, ValidationError, field_validator, model_validator
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from quality_weaver.models import StrictModel


class ExportFormat(StrEnum):
    MARKDOWN = "markdown"
    EXCEL = "excel"


class ProfileError(ValueError):
    """A deterministic profile lookup or validation failure."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


class OrganizationMetadata(StrictModel):
    project_cell: str
    manager_cell: str | None = None
    quality_lead_cell: str | None = None


class WorkbookColumns(StrictModel):
    id: int = Field(gt=0)
    title: int = Field(gt=0)
    traceability: int = Field(gt=0)
    preconditions: int = Field(gt=0)
    steps: int = Field(gt=0)
    expected: int = Field(gt=0)


class WorkbookHeaders(StrictModel):
    id: str
    title: str
    traceability: str
    preconditions: str
    steps: str
    expected: str


class WorkbookProfile(StrictModel):
    template: str
    required_sheets: tuple[str, ...] = Field(min_length=1)
    sheet: str
    header_row: int = Field(gt=0)
    first_row: int = Field(gt=0)
    columns: WorkbookColumns
    headers: WorkbookHeaders
    filename: str

    @field_validator("template")
    @classmethod
    def relative_template(cls, value: str) -> str:
        if not value or Path(value).is_absolute():
            raise ValueError("template must be a nonempty relative path")
        return value

    @field_validator("filename")
    @classmethod
    def safe_filename_policy(cls, value: str) -> str:
        try:
            parsed = tuple(Formatter().parse(value))
        except ValueError as error:
            raise ValueError("filename is not a valid format pattern") from error
        fields: list[str] = []
        for _, field_name, format_spec, conversion in parsed:
            if field_name is None:
                continue
            if field_name not in {"project", "artifact"}:
                raise ValueError("filename fields must be project or artifact")
            if format_spec or conversion is not None:
                raise ValueError("filename fields cannot use conversions or format specs")
            fields.append(field_name)
        if set(fields) != {"project", "artifact"}:
            raise ValueError("filename must contain project and artifact fields")
        return value

    @field_validator("required_sheets")
    @classmethod
    def unique_required_sheets(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("required_sheets must be unique")
        return value

    @model_validator(mode="after")
    def writing_sheet_is_required(self) -> Self:
        if self.sheet not in self.required_sheets:
            raise ValueError("sheet must appear in required_sheets")
        columns = tuple(self.columns.model_dump().values())
        if len(columns) != len(set(columns)):
            raise ValueError("column mappings must be unique")
        if self.header_row >= self.first_row:
            raise ValueError("header_row must precede first_row")
        return self

    def template_path(self, profile_root: Path) -> Path:
        return (profile_root / self.template).resolve()


class Profile(StrictModel):
    schema_version: Literal[1]
    name: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    formats: tuple[ExportFormat, ...] = Field(min_length=1)
    organization: OrganizationMetadata | None = None
    workbooks: dict[str, WorkbookProfile] = Field(default_factory=dict)
    _root: Path = PrivateAttr(default=Path("."))

    @property
    def root(self) -> Path:
        return self._root

    @field_validator("formats")
    @classmethod
    def unique_formats(cls, value: tuple[ExportFormat, ...]) -> tuple[ExportFormat, ...]:
        if len(value) != len(set(value)):
            raise ValueError("formats must be unique")
        return value

    @model_validator(mode="after")
    def excel_has_workbooks(self) -> Self:
        if "excel" in self.formats and not self.workbooks:
            raise ValueError("excel profiles require workbooks")
        if "excel" not in self.formats and self.workbooks:
            raise ValueError("workbooks require the excel format")
        return self

    @classmethod
    def load(cls, name: str, profiles_root: Path) -> Self:
        resolved_profiles_root = profiles_root.resolve()
        if re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) is None:
            raise ProfileError("PROFILE_UNKNOWN", f"unknown profile: {name}")
        profile_root = (resolved_profiles_root / name).resolve()
        if not profile_root.is_relative_to(resolved_profiles_root):
            raise ProfileError("PROFILE_UNKNOWN", f"unknown profile: {name}")
        profile_path = profile_root / "profile.yaml"
        if not profile_path.is_file():
            raise ProfileError("PROFILE_UNKNOWN", f"unknown profile: {name}")
        resolved_profile_path = profile_path.resolve()
        if not resolved_profile_path.is_relative_to(profile_root):
            raise ProfileError(
                "PROFILE_FILE_ESCAPE",
                f"profile file escapes profile root: {name}",
            )

        try:
            document: Any = YAML(typ="safe").load(
                resolved_profile_path.read_text(encoding="utf-8")
            )
            profile = cls.model_validate(document)
        except (OSError, ValidationError, ValueError, YAMLError) as error:
            message = str(error).splitlines()[0]
            raise ProfileError("PROFILE_SCHEMA_INVALID", message) from error
        if profile.name != name:
            raise ProfileError(
                "PROFILE_NAME_MISMATCH",
                f"profile name {profile.name} does not match directory {name}",
            )

        for workbook in profile.workbooks.values():
            template_path = workbook.template_path(profile_root)
            if not template_path.is_relative_to(profile_root):
                raise ProfileError(
                    "PROFILE_TEMPLATE_ESCAPE",
                    f"template escapes profile root: {workbook.template}",
                )
            if not template_path.is_file():
                raise ProfileError(
                    "PROFILE_TEMPLATE_MISSING",
                    f"template does not exist: {workbook.template}",
                )
        profile._root = profile_root
        return profile
