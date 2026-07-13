import hashlib
import json
from collections.abc import Callable
from contextlib import suppress
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError, model_validator

from quality_weaver.io import atomic_create_text, atomic_write_text, exclusive_lock
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

    @model_validator(mode="after")
    def approval_dependencies_are_possible(self) -> "WorkspaceState":
        if (
            self.coverage is ApprovalStatus.APPROVED
            and self.requirements is not ApprovalStatus.APPROVED
        ):
            raise ValueError("approved coverage requires approved requirements")
        if self.testcases is ApprovalStatus.APPROVED and (
            self.requirements is not ApprovalStatus.APPROVED
            or self.coverage is not ApprovalStatus.APPROVED
        ):
            raise ValueError("approved testcases require approved requirements and coverage")
        return self


class Workspace:
    def __init__(self, project_path: Path) -> None:
        self.project_path = project_path
        self.path = project_path / ".quality-weaver"
        self.state_path = self.path / "state.json"
        self._mutation_lock_path = project_path / ".quality-weaver.state.lock"
        self._init_lock_path = project_path / ".quality-weaver.init.lock"

    @classmethod
    def init(cls, project_path: Path) -> "Workspace":
        project_path.mkdir(parents=True, exist_ok=True)
        workspace = cls(project_path)
        with exclusive_lock(workspace._init_lock_path):
            if workspace.state_path.is_file():
                raise StateError(f"workspace state already exists: {workspace.state_path}")
            workspace._initialize_exclusively()
        return workspace

    def _initialize_exclusively(self) -> None:
        created_directories: list[Path] = []
        created_config = False
        config_path = self.path / "config.yaml"
        config_content = "schema_version: 1\nprofile: generic\n"
        try:
            for directory in self._workspace_directories():
                try:
                    directory.mkdir()
                except FileExistsError:
                    continue
                created_directories.append(directory)

            if not config_path.exists():
                try:
                    atomic_create_text(config_path, config_content)
                except FileExistsError:
                    pass
                else:
                    created_config = True

            try:
                atomic_create_text(self.state_path, self._state_content(WorkspaceState()))
            except FileExistsError as error:
                raise StateError(f"workspace state already exists: {self.state_path}") from error
        except BaseException:
            if created_config:
                with suppress(OSError):
                    if config_path.read_text(encoding="utf-8") == config_content:
                        config_path.unlink()
            for directory in reversed(created_directories):
                with suppress(OSError):
                    directory.rmdir()
            raise

    def _workspace_directories(self) -> tuple[Path, ...]:
        return tuple(
            self.path / relative_path
            for relative_path in (
                ".",
                "normalized",
                "questions",
                "coverage",
                "tests",
                "tests/outlines",
                "tests/detailed",
                "exports",
                "runs",
            )
        )

    def load_state(self) -> WorkspaceState:
        try:
            return WorkspaceState.model_validate_json(self.state_path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise StateError(f"workspace state does not exist: {self.state_path}") from error
        except (ValidationError, ValueError) as error:
            raise StateError(f"invalid workspace state: {error}") from error

    def approve(self, stage: Stage) -> None:
        def transition(state: WorkspaceState) -> None:
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

        self._mutate_state(transition)

    def invalidate_after(self, stage: Stage) -> None:
        downstream = {
            Stage.REQUIREMENTS: (Stage.COVERAGE, Stage.TESTCASES),
            Stage.COVERAGE: (Stage.TESTCASES,),
            Stage.TESTCASES: (),
        }

        def transition(state: WorkspaceState) -> None:
            for downstream_stage in downstream[stage]:
                setattr(state, downstream_stage.value, ApprovalStatus.STALE)

        self._mutate_state(transition)

    def regenerate(self, stage: Stage) -> None:
        downstream = {
            Stage.REQUIREMENTS: (Stage.COVERAGE, Stage.TESTCASES),
            Stage.COVERAGE: (Stage.TESTCASES,),
            Stage.TESTCASES: (),
        }

        def transition(state: WorkspaceState) -> None:
            current_status = getattr(state, stage.value)
            if current_status is not ApprovalStatus.STALE:
                raise StateError(
                    f"{stage.value} must be stale before regeneration; "
                    f"current status is {current_status.value}"
                )
            setattr(state, stage.value, ApprovalStatus.DRAFT)
            for downstream_stage in downstream[stage]:
                setattr(state, downstream_stage.value, ApprovalStatus.STALE)

        self._mutate_state(transition)

    def ensure_export_ready(self) -> None:
        state = self.load_state()
        statuses = (state.requirements, state.coverage, state.testcases)
        if any(status is not ApprovalStatus.APPROVED for status in statuses):
            raise StateError("all approval gates must be approved before export")

    def next_action(self, state: WorkspaceState | None = None) -> str:
        state = state or self.load_state()
        for stage in Stage:
            status = getattr(state, stage.value)
            if status is ApprovalStatus.STALE:
                return f"regenerate {stage.value}"
            if status is ApprovalStatus.DRAFT:
                return f"approve {stage.value}"
        return "export"

    def _save_state(self, state: WorkspaceState) -> None:
        atomic_write_text(self.state_path, self._state_content(state))

    def _mutate_state(self, transition: Callable[[WorkspaceState], None]) -> None:
        with exclusive_lock(self._mutation_lock_path):
            state = self.load_state()
            transition(state)
            validated_state = WorkspaceState.model_validate(state.model_dump())
            self._save_state(validated_state)

    @staticmethod
    def _state_content(state: WorkspaceState) -> str:
        return json.dumps(state.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
