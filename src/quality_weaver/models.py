from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ApprovalStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    STALE = "stale"


class CoverageDecision(StrEnum):
    INCLUDE = "include"
    EXCLUDE = "exclude"
    NEEDS_CLARIFICATION = "needs-clarification"


class RequirementEntity(StrictModel):
    id: str = Field(pattern=r"^[A-Z]+-[A-Z0-9-]+$")
    type: str
    name: str
    facts: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    source_quote: str


class RequirementDocument(StrictModel):
    id: str = Field(pattern=r"^REQ-[A-Z0-9-]+$")
    title: str
    source_path: str
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    status: ApprovalStatus = ApprovalStatus.DRAFT
    entities: list[RequirementEntity]
    business_rules: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)


class ViewpointScope(StrEnum):
    LOCAL = "local"
    CROSS_REQUIREMENT = "cross-requirement"
    SYSTEM_WIDE = "system-wide"


class Viewpoint(StrictModel):
    id: str = Field(pattern=r"^VP-[A-Z0-9-]+$")
    name: str
    group: str
    scope: ViewpointScope
    applies_to: list[str]
    signals: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    clarification_prompts: list[str] = Field(default_factory=list)
    default_priority: Literal["high", "medium", "low"]
    guidance: str


class CoverageItem(StrictModel):
    id: str = Field(pattern=r"^COV-[0-9]{3,}$")
    requirement_id: str
    target_id: str
    viewpoint_id: str
    condition: str
    decision: CoverageDecision
    priority: Literal["high", "medium", "low"]
    evidence: str
    rationale: str
    question_id: str | None = None

    @property
    def logical_key(self) -> tuple[str, str, str, str]:
        return (self.requirement_id, self.target_id, self.viewpoint_id, self.condition)


class CoverageLedger(StrictModel):
    status: ApprovalStatus = ApprovalStatus.DRAFT
    catalog_version: str
    profile: str = "generic"
    items: list[CoverageItem]

    @model_validator(mode="after")
    def unique_logical_keys(self) -> "CoverageLedger":
        keys = [item.logical_key for item in self.items]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate coverage logical key")
        return self


class OutlineItem(StrictModel):
    id: str = Field(pattern=r"^OUT-[0-9]{3,}$")
    title: str
    coverage_ids: list[str] = Field(min_length=1)


class TestOutline(StrictModel):
    status: ApprovalStatus = ApprovalStatus.DRAFT
    items: list[OutlineItem]


class TestStep(StrictModel):
    action: str
    expected: str


class TestCase(StrictModel):
    id: str = Field(pattern=r"^TC-[0-9]{3,}$")
    title: str
    outline_id: str
    coverage_ids: list[str] = Field(min_length=1)
    preconditions: list[str]
    test_data: list[str] = Field(default_factory=list)
    steps: list[TestStep] = Field(min_length=1)
    priority: Literal["high", "medium", "low"]
    tags: list[str] = Field(default_factory=list)


class TestCaseDocument(StrictModel):
    status: ApprovalStatus = ApprovalStatus.DRAFT
    cases: list[TestCase]
