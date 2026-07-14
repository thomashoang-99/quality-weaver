# QualityWeaver v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a dual-platform manual test-design plugin that converts Markdown requirements into approved, viewpoint-driven coverage, traceable test cases, canonical Markdown, and profile-driven Excel exports.

**Architecture:** A Python CLI owns schemas, workspace state, validation, projections, and exporters. Shared Agent Skills coordinate Codex and Claude Code but call the same CLI. Viewpoints are reusable knowledge, the Coverage Ledger is the project source of truth, and the Test Map is a deterministic projection.

**Tech Stack:** Python 3.11+, Pydantic 2, Typer, ruamel.yaml, openpyxl, pytest, pytest-cov, Ruff, mypy.

## Global Constraints

- Accept Markdown requirement input only in v1.
- Support Codex and Claude Code through shared `skills/` content and separate manifests.
- Require approval at requirement analysis, coverage design, and detailed testcase stages.
- Treat Markdown testcase files as canonical; Excel is a profile-driven output.
- Never modify the sibling `qa-engine/` repository.
- Never let a model author Test Map decisions independently of the Coverage Ledger.
- Require Python 3.11 or newer.
- Limit model repair retries to two per generation run.

---

## File map

- `pyproject.toml`: package metadata, dependencies, CLI entry point, and tool configuration.
- `src/quality_weaver/cli.py`: public Typer command tree.
- `src/quality_weaver/models.py`: canonical Pydantic models and enums.
- `src/quality_weaver/io.py`: round-trip-safe YAML and atomic JSON/Markdown writes.
- `src/quality_weaver/workspace.py`: workspace creation, state transitions, hashes, and staleness.
- `src/quality_weaver/catalog.py`: viewpoint catalog loading and routing.
- `src/quality_weaver/coverage.py`: ledger validation, uniqueness, completeness, and outline consumption.
- `src/quality_weaver/testmap.py`: deterministic Test Map projection.
- `src/quality_weaver/testcases.py`: outline/detail validation and canonical Markdown rendering.
- `src/quality_weaver/exporters.py`: generic Markdown and profile-selected Excel export.
- `viewpoints/`: portable viewpoint catalog and migrated knowledge.
- `profiles/`: generic and legacy-company output policies.
- `skills/`: shared Codex/Claude workflows.
- `.codex-plugin/plugin.json`, `.claude-plugin/plugin.json`: platform manifests.
- `tests/unit/`: deterministic unit tests.
- `tests/contract/`: schemas, manifests, skill, and workspace contracts.
- `tests/golden/`: end-to-end fixed artifact fixtures.
- `tests/platform/`: Codex and Claude plugin discovery smoke tests.

### Task 1: Package foundation and CLI smoke path

**Files:**
- Create: `pyproject.toml`
- Create: `src/quality_weaver/__init__.py`
- Create: `src/quality_weaver/cli.py`
- Create: `tests/unit/test_cli.py`

**Interfaces:**
- Produces: console command `quality-weaver`, function `quality_weaver.cli.app`.
- Consumes: no earlier task interfaces.

- [ ] **Step 1: Write the failing CLI test**

```python
from typer.testing import CliRunner

from quality_weaver.cli import app


def test_version_command() -> None:
    result = CliRunner().invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "quality-weaver 0.1.0"
```

- [ ] **Step 2: Run the test and verify collection fails**

Run: `python -m pytest tests/unit/test_cli.py -q`

Expected: FAIL because `quality_weaver.cli` does not exist.

- [ ] **Step 3: Add package metadata and minimal CLI**

```toml
[build-system]
requires = ["hatchling>=1.27"]
build-backend = "hatchling.build"

[project]
name = "quality-weaver"
version = "0.1.0"
description = "Viewpoint-driven manual test design workflow"
requires-python = ">=3.11"
dependencies = [
  "openpyxl>=3.1,<4",
  "pydantic>=2.11,<3",
  "ruamel.yaml>=0.18,<0.19",
  "typer>=0.16,<1",
]

[project.optional-dependencies]
dev = [
  "build>=1.2,<2",
  "mypy>=1.16,<2",
  "pytest>=8.4,<9",
  "pytest-cov>=6.2,<7",
  "ruff>=0.12,<1",
]

[project.scripts]
quality-weaver = "quality_weaver.cli:app"

[tool.hatch.build.targets.wheel]
packages = ["src/quality_weaver"]

[tool.pytest.ini_options]
addopts = "-ra"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.mypy]
python_version = "3.11"
strict = true
packages = ["quality_weaver"]
```

```python
# src/quality_weaver/__init__.py
__version__ = "0.1.0"
```

```python
# src/quality_weaver/cli.py
import typer

from quality_weaver import __version__

app = typer.Typer(no_args_is_help=True)


@app.command()
def version() -> None:
    """Print the installed QualityWeaver version."""
    typer.echo(f"quality-weaver {__version__}")
```

- [ ] **Step 4: Install and verify the CLI**

Run: `python -m pip install -e ".[dev]"`

Expected: editable installation succeeds.

Run: `python -m pytest tests/unit/test_cli.py -q`

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/quality_weaver tests/unit/test_cli.py
git commit -m "build: scaffold Python CLI"
```

### Task 2: Canonical domain models and generated schemas

**Files:**
- Create: `src/quality_weaver/models.py`
- Create: `src/quality_weaver/schema.py`
- Create: `schemas/requirement.schema.json`
- Create: `schemas/coverage-ledger.schema.json`
- Create: `schemas/test-outline.schema.json`
- Create: `schemas/testcase.schema.json`
- Create: `tests/unit/test_models.py`
- Create: `tests/contract/test_schemas.py`

**Interfaces:**
- Produces: `RequirementDocument`, `Viewpoint`, `CoverageLedger`, `TestOutline`, `TestCaseDocument`, and `write_schemas(Path)`.
- Consumes: package foundation from Task 1.

- [ ] **Step 1: Write model invariants as failing tests**

```python
import pytest
from pydantic import ValidationError

from quality_weaver.models import CoverageDecision, CoverageItem, CoverageLedger


def test_coverage_logical_key_must_be_unique() -> None:
    item = CoverageItem(
        id="COV-001",
        requirement_id="REQ-001",
        target_id="CTRL-EMAIL",
        viewpoint_id="VP-INPUT-REQUIRED",
        condition="empty",
        decision=CoverageDecision.INCLUDE,
        priority="high",
        evidence="Email is required",
        rationale="Required input",
    )
    with pytest.raises(ValidationError, match="duplicate coverage logical key"):
        CoverageLedger(items=[item, item.model_copy(update={"id": "COV-002"})])
```

- [ ] **Step 2: Verify the test fails**

Run: `python -m pytest tests/unit/test_models.py -q`

Expected: FAIL because canonical models do not exist.

- [ ] **Step 3: Implement typed models**

Implement these exact public types in `models.py`:

```python
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
```

- [ ] **Step 4: Generate and contract-test JSON Schemas**

`write_schemas(output_dir)` writes `model_json_schema()` results with UTF-8, sorted keys, and a final newline. The contract test regenerates into `tmp_path` and asserts byte equality with all four committed schema files.

Run: `python -m quality_weaver.schema schemas`

Expected: four schema files are created.

Run: `python -m pytest tests/unit/test_models.py tests/contract/test_schemas.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/quality_weaver/models.py src/quality_weaver/schema.py schemas tests
git commit -m "feat(domain): define canonical artifacts"
```

### Task 3: Atomic workspace and three-gate state machine

> **Plan update (2026-07-14):** The project is still being built and no real requirement
> documents flow through the workspace yet. Task 3 is adjusted as follows:
>
> 1. **Hash-based staleness detection is deferred.** Keep `WorkspaceState.upstream_hashes`
>    and `sha256_file` as data plumbing, but do not implement automatic hash comparison or
>    auto-invalidation in v1. Manual `invalidate_after` remains the only staleness trigger.
>    As a consequence, `regenerate requirements` stays unreachable in v1 — this is
>    intentional. Revisit both when real requirement inputs exist (v1.x follow-up task).
> 2. **Housekeeping:** add `.quality-weaver.lock` to the repository `.gitignore` and to the
>    workspace documentation, since the project-local lock file persists at the project root.
> 3. **Verification uses fixtures, not real requirements.** Task 3 (and downstream tasks)
>    verify workspace behavior with `tmp_path` fixtures and committed test data instead of
>    live requirement documents; keep it that way until the golden vertical slice in Task 9.

**Files:**
- Create: `src/quality_weaver/io.py`
- Create: `src/quality_weaver/workspace.py`
- Create: `tests/unit/test_workspace.py`
- Modify: `src/quality_weaver/cli.py`

**Interfaces:**
- Produces: `Workspace.init`, `Workspace.load_state`, `Workspace.approve`, `Workspace.invalidate_after`, `sha256_file`.
- Consumes: `ApprovalStatus` from Task 2.

- [ ] **Step 1: Write failing transition tests**

```python
import pytest

from quality_weaver.workspace import Stage, StateError, Workspace


def test_coverage_cannot_be_approved_before_requirements(tmp_path) -> None:
    workspace = Workspace.init(tmp_path)
    with pytest.raises(StateError, match="requirements must be approved"):
        workspace.approve(Stage.COVERAGE)


def test_upstream_change_marks_downstream_stale(tmp_path) -> None:
    workspace = Workspace.init(tmp_path)
    workspace.approve(Stage.REQUIREMENTS)
    workspace.approve(Stage.COVERAGE)
    workspace.invalidate_after(Stage.REQUIREMENTS)
    assert workspace.load_state().coverage == "stale"
```

- [ ] **Step 2: Verify the tests fail**

Run: `python -m pytest tests/unit/test_workspace.py -q`

Expected: FAIL because `Workspace` does not exist.

- [ ] **Step 3: Implement state and atomic IO**

Use an enum with `requirements`, `coverage`, and `testcases`. Store `state.json` with schema version `1`, each gate status, upstream hashes, and last run ID. Write state to a sibling temporary file and replace the destination atomically with `Path.replace`.

`Workspace.init(PATH)` requires `PATH` to already exist as a directory and never creates the
project root or ancestors. Initialization and state mutations use one OS-released project-local
lock at `PATH/.quality-weaver.lock`, keyed by the resolved path with platform-normalized case.

Legal approvals are:

```text
requirements: draft -> approved
coverage: draft -> approved only when requirements=approved
testcases: draft -> approved only when coverage=approved
```

Invalidating requirements marks coverage and testcases stale. Invalidating coverage marks testcases stale. Export requires all three statuses to be approved.

- [ ] **Step 4: Add CLI commands**

```text
quality-weaver init [PATH]
quality-weaver status [PATH]
quality-weaver approve requirements|coverage|testcases [PATH]
```

`init` requires an existing project directory, creates the exact workspace tree inside it, never
creates the project root or ancestors, and refuses to overwrite an existing state file. `status`
emits a compact table and the next legal action.

- [ ] **Step 5: Run verification**

Run: `python -m pytest tests/unit/test_workspace.py tests/unit/test_cli.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/quality_weaver/io.py src/quality_weaver/workspace.py src/quality_weaver/cli.py tests
git commit -m "feat(workspace): enforce approval gates"
```

### Task 4: Viewpoint catalog and selective legacy migration

**Files:**
- Create: `src/quality_weaver/catalog.py`
- Create: `viewpoints/catalog.yaml`
- Create: `viewpoints/local/ui-layout.yaml`
- Create: `viewpoints/local/display-controls.yaml`
- Create: `viewpoints/local/data-visualization.yaml`
- Create: `viewpoints/local/container-structural.yaml`
- Create: `viewpoints/local/input-validation.yaml`
- Create: `viewpoints/local/action-controls.yaml`
- Create: `viewpoints/local/advanced.yaml`
- Create: `viewpoints/local/api.yaml`
- Create: `viewpoints/local/keyboard-mouse.yaml`
- Create: `viewpoints/cross-requirement/navigation.yaml`
- Create: `viewpoints/cross-requirement/data-continuity.yaml`
- Create: `viewpoints/cross-requirement/it-flow.yaml`
- Create: `viewpoints/cross-requirement/e2e-journey.yaml`
- Create: `viewpoints/system-wide/mobile.yaml`
- Create: `viewpoints/system-wide/batch-job-cron.yaml`
- Create: `docs/migration/viewpoint-provenance.yaml`
- Create: `tests/unit/test_catalog.py`
- Create: `tests/contract/test_viewpoint_catalog.py`

**Interfaces:**
- Produces: `Catalog.load(root)`, `Catalog.route(entity_types, risks, enabled_groups)`, `Catalog.get(viewpoint_id)`.
- Consumes: `Viewpoint` and `ViewpointScope` from Task 2.

- [ ] **Step 1: Write catalog contract tests**

```python
from pathlib import Path

from quality_weaver.catalog import Catalog


def test_textbox_routes_only_relevant_groups() -> None:
    catalog = Catalog.load(Path("viewpoints"))
    groups = catalog.route(entity_types={"textbox"}, risks=set(), enabled_groups=set())
    assert "input-validation" in groups
    assert "batch-job" not in groups


def test_all_viewpoint_ids_are_unique() -> None:
    catalog = Catalog.load(Path("viewpoints"))
    ids = [viewpoint.id for viewpoint in catalog.viewpoints]
    assert len(ids) == len(set(ids))
```

- [ ] **Step 2: Verify catalog tests fail**

Run: `python -m pytest tests/unit/test_catalog.py tests/contract/test_viewpoint_catalog.py -q`

Expected: FAIL because the catalog is absent.

- [ ] **Step 3: Build the routing index and migrated files**

Each YAML document validates as `list[Viewpoint]`. `catalog.yaml` contains catalog version `1.0.0` and group routing metadata. Migrate every current table row from all 14 files under `qa-engine/qc-testcase/rules/viewpoints/` into stable atomic viewpoints without copying group prose. Every legacy row must appear in `viewpoint-provenance.yaml` as either a migrated stable ID or an explicit deduplication mapping to another stable ID; no row may be silently dropped. Provenance records the legacy relative path, heading, and row description.

The initial catalog must preserve the full useful legacy viewpoint inventory while reclassifying each item as local, cross-requirement, or system-wide. It must include input required/empty/boundary checks, repeated action/double submit, initial display/empty state, correct navigation/back behavior, cross-screen data continuity, interruption, orientation, permission, and deep-link mobile behavior.

- [ ] **Step 4: Validate without modifying legacy source**

Run: `python -m pytest tests/unit/test_catalog.py tests/contract/test_viewpoint_catalog.py -q`

Expected: all tests pass.

Run: `git -C ../qa-engine status --porcelain`

Expected: no output.

- [ ] **Step 5: Commit**

```bash
git add src/quality_weaver/catalog.py viewpoints docs/migration tests
git commit -m "feat(viewpoints): add routed catalog"
```

### Task 5: Coverage Ledger validation and Test Map projection

**Files:**
- Create: `src/quality_weaver/coverage.py`
- Create: `src/quality_weaver/testmap.py`
- Create: `tests/unit/test_coverage.py`
- Create: `tests/unit/test_testmap.py`
- Modify: `src/quality_weaver/cli.py`

**Interfaces:**
- Produces: `validate_ledger`, `validate_outline_consumption`, `render_testmap`.
- Consumes: canonical models, catalog, and workspace from Tasks 2-4.

- [ ] **Step 1: Write failing coverage tests**

```python
from quality_weaver.coverage import validate_ledger


def test_clarification_requires_question_id(ledger_factory) -> None:
    ledger = ledger_factory(decision="needs-clarification", question_id=None)
    findings = validate_ledger(ledger)
    assert [(item.code, item.blocking) for item in findings] == [
        ("COVERAGE_QUESTION_REQUIRED", True)
    ]
```

Write projection tests that assert rows and counts are sorted deterministically and that the Markdown contains only ledger-derived values.

- [ ] **Step 2: Verify the tests fail**

Run: `python -m pytest tests/unit/test_coverage.py tests/unit/test_testmap.py -q`

Expected: FAIL because coverage validation and projection do not exist.

- [ ] **Step 3: Implement deterministic checks**

Return typed findings with `code`, `message`, `artifact_id`, and `blocking`. Implement these blocking codes:

```text
COVERAGE_DUPLICATE_KEY
COVERAGE_UNKNOWN_REQUIREMENT
COVERAGE_UNKNOWN_TARGET
COVERAGE_UNKNOWN_VIEWPOINT
COVERAGE_EVIDENCE_REQUIRED
COVERAGE_QUESTION_REQUIRED
COVERAGE_UNRESOLVED
COVERAGE_NOT_CONSUMED
COVERAGE_CONSUMED_TWICE
```

- [ ] **Step 4: Implement Test Map rendering**

Render fixed columns `Unit`, `Applicable`, `Included`, `Excluded`, `Questions`, `High`, `Medium`, `Low`, and `Status`, followed by a viewpoint-group matrix and anomaly list. Sort units, groups, and finding codes lexicographically. Include links or textual references to coverage IDs; never ask a model for values.

- [ ] **Step 5: Add CLI commands and verify**

```text
quality-weaver coverage validate .quality-weaver/coverage/ledger.yaml
quality-weaver testmap render .quality-weaver/coverage/ledger.yaml --out .quality-weaver/coverage/test-map.md
```

Run: `python -m pytest tests/unit/test_coverage.py tests/unit/test_testmap.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/quality_weaver/coverage.py src/quality_weaver/testmap.py src/quality_weaver/cli.py tests
git commit -m "feat(coverage): validate and project ledger"
```

### Task 6: Outline, detailed cases, and canonical Markdown

**Files:**
- Create: `src/quality_weaver/testcases.py`
- Create: `tests/unit/test_testcases.py`
- Create: `tests/golden/expected/testcases.md`
- Modify: `src/quality_weaver/cli.py`

**Interfaces:**
- Produces: `validate_outline`, `validate_testcases`, `render_testcases_markdown`.
- Consumes: `CoverageLedger`, `TestOutline`, and `TestCaseDocument`.

- [ ] **Step 1: Write failing traceability tests**

```python
from quality_weaver.testcases import validate_outline


def test_outline_cannot_reference_excluded_coverage(approved_ledger, outline_factory) -> None:
    outline = outline_factory(coverage_ids=["COV-EXCLUDED"])
    findings = validate_outline(approved_ledger, outline)
    assert findings[0].code == "OUTLINE_COVERAGE_NOT_INCLUDED"
    assert findings[0].blocking is True
```

Also test missing coverage, double consumption, unknown outline IDs, mismatched detail coverage, empty actions, empty expected results, and stable Markdown ordering.

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest tests/unit/test_testcases.py -q`

Expected: FAIL because testcase functions do not exist.

- [ ] **Step 3: Implement validators and renderer**

The renderer emits YAML frontmatter followed by one `## TC-NNN: Title` section per case. Each section contains requirement/coverage traceability, priority, preconditions, test data, and a `Step | Action | Expected Result` table. Escape Markdown pipes and normalize newlines deterministically.

- [ ] **Step 4: Add CLI validation/render commands**

```text
quality-weaver outline validate LEDGER OUTLINE
quality-weaver testcases validate LEDGER OUTLINE CASES
quality-weaver testcases render CASES --out testcases.md
```

- [ ] **Step 5: Verify golden output**

Run: `python -m pytest tests/unit/test_testcases.py tests/golden -q`

Expected: all tests pass and rendered bytes match the committed golden Markdown.

- [ ] **Step 6: Commit**

```bash
git add src/quality_weaver/testcases.py src/quality_weaver/cli.py tests
git commit -m "feat(testcases): enforce traceable cases"
```

### Task 7: Generic and legacy-company export profiles

**Files:**
- Create: `src/quality_weaver/profiles.py`
- Create: `src/quality_weaver/exporters.py`
- Create: `profiles/generic/profile.yaml`
- Create: `profiles/company-legacy/profile.yaml`
- Copy: `qa-engine/qc-testcase/templates/UT_TestCase.xlsx` to `profiles/company-legacy/templates/UT_TestCase.xlsx`
- Copy: `qa-engine/qc-testcase/templates/IT_TestCase.xlsx` to `profiles/company-legacy/templates/IT_TestCase.xlsx`
- Create: `tests/unit/test_profiles.py`
- Create: `tests/unit/test_exporters.py`
- Modify: `src/quality_weaver/cli.py`

**Interfaces:**
- Produces: `Profile.load`, `export_markdown`, `export_excel`.
- Consumes: approved `TestCaseDocument` and workspace state.

- [ ] **Step 1: Write failing profile/export tests**

Test unknown profile rejection, schema-invalid profile rejection, export blocked before all three approvals, generic Markdown byte equality, workbook case count, filename policy, and preservation of source template files.

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest tests/unit/test_profiles.py tests/unit/test_exporters.py -q`

Expected: FAIL because profiles and exporters do not exist.

- [ ] **Step 3: Implement profiles**

The generic profile permits Markdown only. The legacy profile declares workbook paths, required sheet names, column mappings, and filename patterns. Organizational fields remain optional profile metadata and never appear in core models.

- [ ] **Step 4: Port exporter behavior behind the new interface**

Reuse proven parsing and workbook-writing behavior from the legacy repository only after its equivalent regression test exists. Replace Vietnamese hardcoded error messages and filename rules with typed findings and profile configuration. Do not import code from the sibling repository at runtime.

- [ ] **Step 5: Add export command and verify**

```text
quality-weaver export --format markdown --profile generic
quality-weaver export --format excel --profile company-legacy
```

Run: `python -m pytest tests/unit/test_profiles.py tests/unit/test_exporters.py -q`

Expected: all tests pass.

Run: `git -C ../qa-engine status --porcelain`

Expected: no output.

- [ ] **Step 6: Commit**

```bash
git add src/quality_weaver profiles tests
git commit -m "feat(export): add profile-driven outputs"
```

### Task 8: Shared Agent Skills and dual platform manifests

**Files:**
- Create: `.codex-plugin/plugin.json`
- Create: `.claude-plugin/plugin.json`
- Create: `skills/initialize/SKILL.md`
- Create: `skills/analyze-requirements/SKILL.md`
- Create: `skills/plan-coverage/SKILL.md`
- Create: `skills/design-testcases/SKILL.md`
- Create: `skills/export-testcases/SKILL.md`
- Create: `skills/status/SKILL.md`
- Create: `tests/contract/test_skills.py`
- Create: `tests/platform/test_manifests.py`

**Interfaces:**
- Produces: six shared workflows discoverable by Codex and Claude Code.
- Consumes: all public CLI commands from Tasks 1-7.

- [ ] **Step 1: Write failing manifest and skill tests**

```python
import json
from pathlib import Path


def test_both_manifests_have_same_identity() -> None:
    codex = json.loads(Path(".codex-plugin/plugin.json").read_text(encoding="utf-8"))
    claude = json.loads(Path(".claude-plugin/plugin.json").read_text(encoding="utf-8"))
    assert codex["name"] == claude["name"] == "quality-weaver"
    assert codex["version"] == claude["version"] == "0.1.0"
```

Contract tests parse every skill frontmatter, require unique names and descriptions, reject Claude-only or Codex-only metadata in shared files, verify declared input/read paths exist, and verify referenced CLI commands appear in `quality-weaver --help`.

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest tests/contract/test_skills.py tests/platform/test_manifests.py -q`

Expected: FAIL because manifests and skills do not exist.

- [ ] **Step 3: Create both manifests**

Codex manifest:

```json
{
  "name": "quality-weaver",
  "version": "0.1.0",
  "description": "Viewpoint-driven manual test design",
  "skills": "./skills/"
}
```

Claude manifest:

```json
{
  "name": "quality-weaver",
  "version": "0.1.0",
  "description": "Viewpoint-driven manual test design"
}
```

- [ ] **Step 4: Write thin shared skills**

Each skill must declare its input artifacts, allowed state, exact CLI validation command, output artifact, blocking findings, retry limit, and next human gate. Skills never embed schemas, duplicate viewpoint knowledge, write `state.json`, or independently calculate Test Map values.

- [ ] **Step 5: Run platform contracts**

Run: `python -m pytest tests/contract/test_skills.py tests/platform/test_manifests.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add .codex-plugin .claude-plugin skills tests
git commit -m "feat(plugin): support Codex and Claude"
```

### Task 9: Golden vertical slice, model evaluation contract, and documentation

**Files:**
- Create: `examples/login/requirements/login.md`
- Create: `tests/golden/login/normalized.yaml`
- Create: `tests/golden/login/ledger.yaml`
- Create: `tests/golden/login/test-map.md`
- Create: `tests/golden/login/outline.yaml`
- Create: `tests/golden/login/testcases.yaml`
- Create: `tests/golden/test_login_vertical_slice.py`
- Create: `evals/cases/login.yaml`
- Create: `evals/README.md`
- Create: `README.md`
- Create: `CONTRIBUTING.md`
- Create: `AGENTS.md`
- Create: `CLAUDE.md`

**Interfaces:**
- Produces: reproducible v1 example, contributor commands, and model evaluation contract.
- Consumes: complete core and plugin interfaces.

- [ ] **Step 1: Write the failing vertical-slice test**

The test initializes a temporary workspace, loads committed normalized and ledger fixtures, validates coverage, renders Test Map, approves all gates in order, validates outline/cases, renders Markdown, and asserts every generated artifact byte-matches the committed golden file.

- [ ] **Step 2: Verify the vertical slice fails**

Run: `python -m pytest tests/golden/test_login_vertical_slice.py -q`

Expected: FAIL until fixtures and documentation commands are complete.

- [ ] **Step 3: Add the model evaluation contract**

The eval case provides one fixed normalized requirement packet and relevant viewpoint packet. It requires model output to validate against `coverage-ledger.schema.json`. Scores are separated into deterministic structural validity and semantic coverage quality. Run metadata records provider, model string, platform, catalog version, profile, and artifact hash. The acceptance threshold is 100% for schema, uniqueness, traceability, and gate checks; semantic scores are reported rather than used to bypass human approval.

- [ ] **Step 4: Document installation and workflow**

README documents Python installation, local Codex marketplace/plugin setup, Claude `--plugin-dir` development setup, the six skills, the three gates, workspace artifacts, generic export, legacy profile activation, and recovery from stale state. `AGENTS.md` and `CLAUDE.md` contain only repository development commands and conventions; plugin runtime behavior remains in skills.

- [ ] **Step 5: Run full verification**

Run: `python -m ruff check .`

Expected: exit code 0.

Run: `python -m mypy src`

Expected: exit code 0.

Run: `python -m pytest --cov=quality_weaver --cov-report=term-missing -q`

Expected: all tests pass and core package line coverage is at least 90%.

Run: `git -C ../qa-engine status --porcelain`

Expected: no output.

- [ ] **Step 6: Commit**

```bash
git add examples tests/golden evals README.md CONTRIBUTING.md AGENTS.md CLAUDE.md
git commit -m "docs: add verified v1 workflow"
```

### Task 10: Release verification

**Files:**
- Create: `CHANGELOG.md`
- Create: `.github/workflows/ci.yml`
- Modify: `pyproject.toml`

**Interfaces:**
- Produces: repeatable CI and installable v0.1.0 artifacts.
- Consumes: all previous tasks.

- [ ] **Step 1: Add CI before claiming release readiness**

CI runs on Windows and Ubuntu with Python 3.11 and 3.13. Each job installs `.[dev]`, runs Ruff, mypy, all tests, builds wheel/sdist, installs the wheel into a clean environment, and verifies `quality-weaver version`.

- [ ] **Step 2: Add release metadata**

Add project URLs, MIT license metadata, package data for schemas/viewpoints/profiles, and a `0.1.0` changelog entry describing the three-gate viewpoint-driven workflow and both plugin manifests.

- [ ] **Step 3: Run the exact local release checks**

Run: `python -m ruff check .`

Expected: exit code 0.

Run: `python -m mypy src`

Expected: exit code 0.

Run: `python -m pytest --cov=quality_weaver --cov-fail-under=90 -q`

Expected: all tests pass with at least 90% line coverage.

Run: `python -m build`

Expected: one wheel and one source distribution under `dist/`.

- [ ] **Step 4: Verify both plugin structures and legacy cleanliness**

Run: `python -m pytest tests/platform tests/contract -q`

Expected: all tests pass.

Run: `git -C ../qa-engine status --porcelain`

Expected: no output.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/ci.yml CHANGELOG.md pyproject.toml
git commit -m "ci: verify QualityWeaver release"
```

## Plan self-review

- Every design requirement maps to Tasks 1-10.
- The Coverage Ledger remains the only project coverage source of truth.
- The Test Map is generated only by `render_testmap`.
- Codex and Claude share one skill tree and one CLI.
- Legacy files are copied only into a profile or migrated with provenance.
- Every task ends with an independently testable deliverable and commit.
- No implementation step requires modifying `qa-engine`.
