import hashlib
import json
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import pytest

import quality_weaver.io as io_module
import quality_weaver.workspace as workspace_module
from quality_weaver.io import atomic_write_text, exclusive_lock
from quality_weaver.models import ApprovalStatus
from quality_weaver.workspace import Stage, StateError, Workspace, sha256_file


def test_init_creates_exact_workspace_tree_and_initial_state(tmp_path) -> None:
    workspace = Workspace.init(tmp_path)

    assert workspace.path == tmp_path / ".quality-weaver"
    assert {
        path.relative_to(workspace.path).as_posix()
        for path in workspace.path.rglob("*")
    } == {
        "config.yaml",
        "state.json",
        "normalized",
        "questions",
        "coverage",
        "tests",
        "tests/outlines",
        "tests/detailed",
        "exports",
        "runs",
    }
    state = workspace.load_state()
    assert state.schema_version == 1
    assert state.requirements is ApprovalStatus.DRAFT
    assert state.coverage is ApprovalStatus.DRAFT
    assert state.testcases is ApprovalStatus.DRAFT
    assert state.upstream_hashes == {}
    assert state.last_run_id is None


def test_init_refuses_to_overwrite_existing_state(tmp_path) -> None:
    state_path = tmp_path / ".quality-weaver" / "state.json"
    state_path.parent.mkdir()
    state_path.write_text('{"sentinel": true}', encoding="utf-8")

    with pytest.raises(StateError, match="already exists"):
        Workspace.init(tmp_path)

    assert state_path.read_text(encoding="utf-8") == '{"sentinel": true}'


def test_stale_lock_file_does_not_block_new_owner(tmp_path) -> None:
    lock_path = tmp_path / "workspace.lock"
    lock_path.write_text("crashed-owner", encoding="utf-8")

    with exclusive_lock(lock_path, timeout_seconds=0.05):
        assert lock_path.exists()


def test_workspace_translates_lock_timeout_to_state_error(tmp_path, monkeypatch) -> None:
    @contextmanager
    def timed_out_lock(*args, **kwargs):
        raise io_module.LockTimeoutError("timed out")
        yield

    monkeypatch.setattr(workspace_module, "exclusive_lock", timed_out_lock)

    with pytest.raises(StateError, match="timed out acquiring workspace lock"):
        Workspace.init(tmp_path)


def test_workspace_path_aliases_share_the_same_locks(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path.parent)
    relative_path = Path(tmp_path.name)

    absolute_workspace = Workspace(tmp_path)
    relative_workspace = Workspace(relative_path)

    assert relative_workspace._init_lock_path == absolute_workspace._init_lock_path
    assert relative_workspace._mutation_lock_path == absolute_workspace._mutation_lock_path


def test_init_rejects_file_at_expected_directory_and_rolls_back(tmp_path) -> None:
    workspace_path = tmp_path / ".quality-weaver"
    workspace_path.mkdir()
    normalized_path = workspace_path / "normalized"
    normalized_path.write_text("user content", encoding="utf-8")

    with pytest.raises(StateError, match="expected workspace directory"):
        Workspace.init(tmp_path)

    assert normalized_path.read_text(encoding="utf-8") == "user content"
    assert {path.name for path in workspace_path.iterdir()} == {"normalized"}


def test_init_rejects_directory_at_config_path_and_rolls_back(tmp_path) -> None:
    config_path = tmp_path / ".quality-weaver" / "config.yaml"
    config_path.mkdir(parents=True)

    with pytest.raises(StateError, match="config.yaml must be a regular file"):
        Workspace.init(tmp_path)

    assert config_path.is_dir()
    assert {path.name for path in config_path.parent.iterdir()} == {"config.yaml"}


def test_failed_init_removes_newly_created_empty_project_root(tmp_path, monkeypatch) -> None:
    project_path = tmp_path / "new-project"

    def fail_create(*args, **kwargs) -> None:
        raise OSError("state creation failed")

    monkeypatch.setattr(workspace_module, "atomic_create_text", fail_create)

    with pytest.raises(OSError, match="state creation failed"):
        Workspace.init(project_path)

    assert not project_path.exists()


def test_load_state_rejects_unsupported_schema_version(tmp_path) -> None:
    workspace = Workspace.init(tmp_path)
    state = json.loads(workspace.state_path.read_text(encoding="utf-8"))
    state["schema_version"] = 2
    workspace.state_path.write_text(json.dumps(state), encoding="utf-8")

    with pytest.raises(StateError, match="invalid workspace state"):
        workspace.load_state()


@pytest.mark.parametrize(
    ("requirements", "coverage", "testcases"),
    [
        ("draft", "approved", "draft"),
        ("draft", "approved", "approved"),
        ("approved", "draft", "approved"),
    ],
)
def test_load_state_rejects_impossible_approval_dependencies(
    tmp_path, requirements: str, coverage: str, testcases: str
) -> None:
    workspace = Workspace.init(tmp_path)
    state = json.loads(workspace.state_path.read_text(encoding="utf-8"))
    state.update(requirements=requirements, coverage=coverage, testcases=testcases)
    workspace.state_path.write_text(json.dumps(state), encoding="utf-8")

    with pytest.raises(StateError, match="invalid workspace state"):
        workspace.load_state()


def test_coverage_cannot_be_approved_before_requirements(tmp_path) -> None:
    workspace = Workspace.init(tmp_path)

    with pytest.raises(StateError, match="requirements must be approved"):
        workspace.approve(Stage.COVERAGE)


def test_testcases_cannot_be_approved_before_coverage(tmp_path) -> None:
    workspace = Workspace.init(tmp_path)
    workspace.approve(Stage.REQUIREMENTS)

    with pytest.raises(StateError, match="coverage must be approved"):
        workspace.approve(Stage.TESTCASES)


def test_gates_can_be_approved_in_order_and_become_export_ready(tmp_path) -> None:
    workspace = Workspace.init(tmp_path)

    workspace.approve(Stage.REQUIREMENTS)
    workspace.approve(Stage.COVERAGE)
    workspace.approve(Stage.TESTCASES)

    state = workspace.load_state()
    assert state.requirements is ApprovalStatus.APPROVED
    assert state.coverage is ApprovalStatus.APPROVED
    assert state.testcases is ApprovalStatus.APPROVED
    workspace.ensure_export_ready()


def test_export_readiness_requires_all_three_approved(tmp_path) -> None:
    workspace = Workspace.init(tmp_path)
    workspace.approve(Stage.REQUIREMENTS)
    workspace.approve(Stage.COVERAGE)

    with pytest.raises(StateError, match="all approval gates must be approved"):
        workspace.ensure_export_ready()


def test_upstream_change_marks_downstream_stale(tmp_path) -> None:
    workspace = Workspace.init(tmp_path)
    workspace.approve(Stage.REQUIREMENTS)
    workspace.approve(Stage.COVERAGE)
    workspace.invalidate_after(Stage.REQUIREMENTS)

    state = workspace.load_state()
    assert state.requirements is ApprovalStatus.APPROVED
    assert state.coverage is ApprovalStatus.STALE
    assert state.testcases is ApprovalStatus.STALE


def test_coverage_change_marks_only_testcases_stale(tmp_path) -> None:
    workspace = Workspace.init(tmp_path)
    workspace.approve(Stage.REQUIREMENTS)
    workspace.approve(Stage.COVERAGE)
    workspace.approve(Stage.TESTCASES)

    workspace.invalidate_after(Stage.COVERAGE)

    state = workspace.load_state()
    assert state.requirements is ApprovalStatus.APPROVED
    assert state.coverage is ApprovalStatus.APPROVED
    assert state.testcases is ApprovalStatus.STALE


def test_regenerate_moves_stale_stage_to_draft_and_keeps_downstream_stale(tmp_path) -> None:
    workspace = Workspace.init(tmp_path)
    workspace.approve(Stage.REQUIREMENTS)
    workspace.approve(Stage.COVERAGE)
    workspace.approve(Stage.TESTCASES)
    workspace.invalidate_after(Stage.REQUIREMENTS)

    workspace.regenerate(Stage.COVERAGE)

    state = workspace.load_state()
    assert state.requirements is ApprovalStatus.APPROVED
    assert state.coverage is ApprovalStatus.DRAFT
    assert state.testcases is ApprovalStatus.STALE


def test_regenerate_rejects_non_stale_stage(tmp_path) -> None:
    workspace = Workspace.init(tmp_path)

    with pytest.raises(StateError, match="must be stale"):
        workspace.regenerate(Stage.REQUIREMENTS)


def test_approve_persists_complete_json_without_leaving_temporary_file(tmp_path) -> None:
    workspace = Workspace.init(tmp_path)

    workspace.approve(Stage.REQUIREMENTS)

    raw_state = json.loads(workspace.state_path.read_text(encoding="utf-8"))
    assert raw_state["requirements"] == "approved"
    assert not workspace.state_path.with_suffix(".json.tmp").exists()


@pytest.mark.parametrize("failure_point", ["write", "replace"])
def test_atomic_write_cleans_unique_temporary_file_after_failure(
    tmp_path, monkeypatch, failure_point: str
) -> None:
    destination = tmp_path / "state.json"
    destination.write_text("original", encoding="utf-8")

    def fail(*args, **kwargs) -> None:
        raise OSError(failure_point)

    if failure_point == "write":
        monkeypatch.setattr(Path, "write_text", fail)
    else:
        monkeypatch.setattr(Path, "replace", fail)

    with pytest.raises(OSError, match=failure_point):
        atomic_write_text(destination, "replacement")

    assert destination.read_text(encoding="utf-8") == "original"
    assert list(tmp_path.glob(".state.json.*.tmp")) == []


def test_concurrent_atomic_writers_use_distinct_temporary_files(tmp_path, monkeypatch) -> None:
    destination = tmp_path / "state.json"
    destination.write_text("initial", encoding="utf-8")
    barrier = threading.Barrier(2)
    original_replace = Path.replace
    attempted_sources: set[Path] = set()
    attempted_sources_lock = threading.Lock()

    def synchronized_replace(source: Path, target: Path) -> Path:
        with attempted_sources_lock:
            first_attempt = source not in attempted_sources
            attempted_sources.add(source)
        if first_attempt:
            barrier.wait(timeout=2)
        return original_replace(source, target)

    monkeypatch.setattr(Path, "replace", synchronized_replace)
    errors: list[BaseException] = []

    def write(content: str) -> None:
        try:
            atomic_write_text(destination, content)
        except BaseException as error:
            errors.append(error)

    threads = [threading.Thread(target=write, args=(content,)) for content in ("one", "two")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=3)

    assert errors == []
    assert len(attempted_sources) == 2
    assert destination.read_text(encoding="utf-8") in {"one", "two"}
    assert list(tmp_path.glob(".state.json.*.tmp")) == []


def test_concurrent_state_mutations_do_not_lose_updates(tmp_path, monkeypatch) -> None:
    workspace = Workspace.init(tmp_path)
    workspace.approve(Stage.REQUIREMENTS)
    original_write = workspace_module.atomic_write_text
    active_writers = 0
    maximum_active_writers = 0
    counter_lock = threading.Lock()

    def observed_write(path: Path, content: str) -> None:
        nonlocal active_writers, maximum_active_writers
        with counter_lock:
            active_writers += 1
            maximum_active_writers = max(maximum_active_writers, active_writers)
        time.sleep(0.05)
        try:
            original_write(path, content)
        finally:
            with counter_lock:
                active_writers -= 1

    monkeypatch.setattr(workspace_module, "atomic_write_text", observed_write)
    errors: list[BaseException] = []

    def mutate(operation) -> None:
        try:
            operation()
        except BaseException as error:
            errors.append(error)

    threads = [
        threading.Thread(target=mutate, args=(lambda: workspace.approve(Stage.COVERAGE),)),
        threading.Thread(
            target=mutate, args=(lambda: workspace.invalidate_after(Stage.COVERAGE),)
        ),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=3)

    state = workspace.load_state()
    assert errors == []
    assert maximum_active_writers == 1
    assert state.coverage is ApprovalStatus.APPROVED
    assert state.testcases is ApprovalStatus.STALE


def test_concurrent_initializers_have_one_winner_without_overwrite(tmp_path, monkeypatch) -> None:
    original_exists = Path.exists
    barrier = threading.Barrier(2)

    def synchronized_exists(path: Path) -> bool:
        if path.name == "state.json":
            barrier.wait(timeout=2)
        return original_exists(path)

    monkeypatch.setattr(Path, "exists", synchronized_exists)
    results: list[Workspace] = []
    errors: list[BaseException] = []

    def initialize() -> None:
        try:
            results.append(Workspace.init(tmp_path))
        except BaseException as error:
            errors.append(error)

    threads = [threading.Thread(target=initialize) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=3)

    assert len(results) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], StateError)
    assert results[0].load_state().requirements is ApprovalStatus.DRAFT


def test_failed_initializer_rolls_back_only_its_created_content(tmp_path, monkeypatch) -> None:
    workspace_path = tmp_path / ".quality-weaver"
    workspace_path.mkdir()
    user_file = workspace_path / "keep.txt"
    user_file.write_text("keep", encoding="utf-8")

    def fail_create(*args, **kwargs) -> None:
        raise OSError("state creation failed")

    monkeypatch.setattr(workspace_module, "atomic_create_text", fail_create, raising=False)

    with pytest.raises(OSError, match="state creation failed"):
        Workspace.init(tmp_path)

    assert user_file.read_text(encoding="utf-8") == "keep"
    assert {path.name for path in workspace_path.iterdir()} == {"keep.txt"}


def test_sha256_file_hashes_bytes(tmp_path) -> None:
    source = tmp_path / "source.md"
    source.write_bytes(b"QualityWeaver\r\n")

    assert sha256_file(source) == hashlib.sha256(b"QualityWeaver\r\n").hexdigest()
