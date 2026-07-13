import hashlib
import json
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError

from quality_weaver.io import atomic_write_text
from quality_weaver.models import ApprovalStatus, StrictModel


class Stage(StrEnum):
    REQUIREMENTS = "requirements"
    COVERAGE = "coverage"
    TESTCASES = "testcases"


class StateError(RuntimeError):
    """Raised when workspace state is missing, invalid, or illegally transitioned."""


class WorkspaceState(StrictModel):
    schema_version: Literal[1] = 1
    requirements: ApprovalStatus = ApprovalStatus.DRAFT
    coverage: ApprovalStatus = ApprovalStatus.DRAFT
    testcases: ApprovalStatus = ApprovalStatus.DRAFT
    upstream_hashes: dict[str, str] = Field(default_factory=dict)
    last_run_id: str | None = None


class Workspace:
    def __init__(self, project_path: Path) -> None:
        self.project_path = project_path
        self.path = project_path / ".quality-weaver"
        self.state_path = self.path / "state.json"

    @classmethod
    def init(cls, project_path: Path) -> "Workspace":
        workspace = cls(project_path)
        if workspace.state_path.exists():
            raise StateError(f"workspace state already exists: {workspace.state_path}")

        workspace.path.mkdir(parents=True, exist_ok=True)
        for relative_path in (
            "normalized",
            "questions",
            "coverage",
            "tests/outlines",
            "tests/detailed",
            "exports",
            "runs",
        ):
            (workspace.path / relative_path).mkdir(parents=True, exist_ok=True)

        config_path = workspace.path / "config.yaml"
        if not config_path.exists():
            config_path.write_text("schema_version: 1\nprofile: generic\n", encoding="utf-8")
        workspace._save_state(WorkspaceState())
        return workspace

    def load_state(self) -> WorkspaceState:
        try:
            return WorkspaceState.model_validate_json(self.state_path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise StateError(f"workspace state does not exist: {self.state_path}") from error
        except (ValidationError, ValueError) as error:
            raise StateError(f"invalid workspace state: {error}") from error

    def approve(self, stage: Stage) -> None:
        state = self.load_state()
        prerequisites = {
            Stage.COVERAGE: Stage.REQUIREMENTS,
            Stage.TESTCASES: Stage.COVERAGE,
        }
        prerequisite = prerequisites.get(stage)
        if prerequisite is not None:
            prerequisite_status = getattr(state, prerequisite.value)
            if prerequisite_status is not ApprovalStatus.APPROVED:
                raise StateError(f"{prerequisite.value} must be approved before {stage.value}")

        current_status = getattr(state, stage.value)
        if current_status is not ApprovalStatus.DRAFT:
            message = (
                f"{stage.value} must be draft before approval; "
                f"current status is {current_status.value}"
            )
            raise StateError(message)
        setattr(state, stage.value, ApprovalStatus.APPROVED)
        self._save_state(state)

    def invalidate_after(self, stage: Stage) -> None:
        state = self.load_state()
        downstream = {
            Stage.REQUIREMENTS: (Stage.COVERAGE, Stage.TESTCASES),
            Stage.COVERAGE: (Stage.TESTCASES,),
            Stage.TESTCASES: (),
        }
        for downstream_stage in downstream[stage]:
            setattr(state, downstream_stage.value, ApprovalStatus.STALE)
        self._save_state(state)

    def ensure_export_ready(self) -> None:
        state = self.load_state()
        statuses = (state.requirements, state.coverage, state.testcases)
        if any(status is not ApprovalStatus.APPROVED for status in statuses):
            raise StateError("all approval gates must be approved before export")

    def next_action(self) -> str:
        state = self.load_state()
        for stage in Stage:
            status = getattr(state, stage.value)
            if status is ApprovalStatus.STALE:
                return f"regenerate {stage.value}"
            if status is ApprovalStatus.DRAFT:
                return f"approve {stage.value}"
        return "export"

    def _save_state(self, state: WorkspaceState) -> None:
        content = json.dumps(state.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
        atomic_write_text(self.state_path, content)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
