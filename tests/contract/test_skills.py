import re
import shlex
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from quality_weaver import models
from quality_weaver.cli import app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = PROJECT_ROOT / "skills"
EXPECTED_SKILLS = {
    "initialize",
    "analyze-requirements",
    "plan-coverage",
    "design-testcases",
    "export-testcases",
    "status",
}
REQUIRED_CONTRACT_LABELS = (
    "Input artifacts and read paths",
    "Allowed state",
    "CLI validation command",
    "Output artifact",
    "Blocking findings",
    "Retry limit",
    "Next human gate",
)
PORTABILITY_VIOLATIONS = (
    "${CLAUDE_PLUGIN_ROOT}",
    "CLAUDE.md",
    "agents/openai.yaml",
)
COMMAND_PATHS = {
    ("version",),
    ("init",),
    ("status",),
    ("approve",),
    ("regenerate",),
    ("reopen",),
    ("export",),
    ("requirements", "validate"),
    ("coverage", "validate"),
    ("testmap", "render"),
    ("outline", "validate"),
    ("testcases", "validate"),
    ("testcases", "render"),
}
POSITIONAL_COUNTS = {
    ("version",): 0,
    ("init",): 1,
    ("status",): 1,
    ("approve",): 2,
    ("regenerate",): 2,
    ("reopen",): 2,
    ("export",): 2,
    ("requirements", "validate"): 1,
    ("coverage", "validate"): 1,
    ("testmap", "render"): 1,
    ("outline", "validate"): 2,
    ("testcases", "validate"): 3,
    ("testcases", "render"): 1,
}


def _skill_paths() -> list[Path]:
    return sorted(SKILLS_ROOT.glob("*/SKILL.md"))


def _parse_skill(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    match = re.fullmatch(r"---\n(.+?)\n---\n(.+)", text, flags=re.DOTALL)
    assert match, f"{path} must contain YAML frontmatter"
    metadata = YAML(typ="safe").load(match.group(1))
    assert isinstance(metadata, dict)
    return metadata, match.group(2)


def _command_path(tokens: list[str]) -> tuple[str, ...]:
    for size in (2, 1):
        candidate = tuple(tokens[1 : size + 1])
        if candidate in COMMAND_PATHS:
            return candidate
    raise AssertionError(f"unknown QualityWeaver command: {' '.join(tokens)}")


def test_expected_shared_skills_exist() -> None:
    assert {path.parent.name for path in _skill_paths()} == EXPECTED_SKILLS


@pytest.mark.parametrize("skill_name", sorted(EXPECTED_SKILLS))
def test_expected_skill_exists(skill_name: str) -> None:
    assert (SKILLS_ROOT / skill_name / "SKILL.md").is_file()


def test_skill_frontmatter_is_portable_and_discoverable() -> None:
    parsed = [_parse_skill(path) for path in _skill_paths()]
    metadata = [item[0] for item in parsed]

    assert all(set(item) == {"name", "description"} for item in metadata)
    assert {item["name"] for item in metadata} == EXPECTED_SKILLS
    assert len({item["description"] for item in metadata}) == len(metadata)
    for item in metadata:
        description = item["description"]
        assert isinstance(description, str)
        assert description.startswith("Use when ")
        assert not re.search(r"\b(I|we|you)\b", description, flags=re.IGNORECASE)


@pytest.mark.parametrize("path", _skill_paths(), ids=lambda path: path.parent.name)
def test_skill_declares_the_complete_workflow_contract(path: Path) -> None:
    _, body = _parse_skill(path)

    for label in REQUIRED_CONTRACT_LABELS:
        assert f"**{label}:**" in body
    assert "Model artifact validation retries:" in body
    assert re.search(r"Model artifact validation retries: (?:0|[12])\b", body)
    assert "Do not write `<project-path>/.quality-weaver/state.json`" in body
    assert "Do not approve a gate" in body
    assert all(token not in body for token in PORTABILITY_VIOLATIONS)


def test_declared_read_paths_are_portable_templates_or_repository_paths() -> None:
    allowed_roots = {
        "<project-path>",
        "<plugin-root>",
    }
    for path in _skill_paths():
        _, body = _parse_skill(path)
        section = body.split("**Input artifacts and read paths:**", 1)[1].split(
            "**Allowed state:**", 1
        )[0]
        declared = re.findall(r"`([^`]+)`", section)
        assert declared, f"{path} must declare at least one input/read path"
        for value in declared:
            assert any(value.startswith(root) for root in allowed_roots), value
            if value.startswith("<plugin-root>/"):
                static_prefix = (
                    value.removeprefix("<plugin-root>/")
                    .split("<", 1)[0]
                    .split("*", 1)[0]
                    .rstrip("/")
                )
                assert (PROJECT_ROOT / static_prefix).exists(), value


def test_project_and_plugin_paths_are_cwd_independent_placeholders() -> None:
    for path in _skill_paths():
        _, body = _parse_skill(path)
        code_spans = re.findall(r"`([^`]+)`", body)
        for value in code_spans:
            if ".quality-weaver/" in value:
                assert "<project-path>/.quality-weaver/" in value, (path, value)
            for resource in ("schemas/", "viewpoints/", "profiles/"):
                if resource in value:
                    assert f"<plugin-root>/{resource}" in value, (path, value)
        assert "--catalog viewpoints" not in body
        assert "quality-weaver testcases validate .quality-weaver/" not in body


def test_absolute_project_and_plugin_paths_work_from_unrelated_cwd(
    tmp_path: Path, monkeypatch
) -> None:
    project = tmp_path / "project"
    unrelated = tmp_path / "unrelated"
    project.mkdir()
    unrelated.mkdir()
    runner = CliRunner()
    initialized = runner.invoke(app, ["init", str(project)])
    assert initialized.exit_code == 0
    requirement_path = project / ".quality-weaver" / "normalized" / "requirement.yaml"
    requirement_path.write_text(
        models.RequirementDocument(
            id="REQ-CWD",
            title="CWD independent",
            source_path="requirements/cwd.md",
            source_sha256="a" * 64,
            entities=[],
        ).model_dump_json(),
        encoding="utf-8",
    )
    ledger_path = project / ".quality-weaver" / "coverage" / "ledger.yaml"
    ledger_path.write_text(
        models.CoverageLedger(catalog_version="1.0.0", items=[]).model_dump_json(),
        encoding="utf-8",
    )
    map_path = project / ".quality-weaver" / "coverage" / "test-map.md"
    monkeypatch.chdir(unrelated)

    requirement = runner.invoke(app, ["requirements", "validate", str(requirement_path)])
    coverage = runner.invoke(
        app,
        [
            "coverage",
            "validate",
            str(ledger_path),
            "--catalog",
            str(PROJECT_ROOT / "viewpoints"),
            "--requirement-id",
            "REQ-CWD",
            "--target",
            "REQ-CWD=TARGET-CWD",
        ],
    )
    projection = runner.invoke(
        app,
        [
            "testmap",
            "render",
            str(ledger_path),
            "--out",
            str(map_path),
            "--catalog",
            str(PROJECT_ROOT / "viewpoints"),
            "--requirement-id",
            "REQ-CWD",
            "--target",
            "REQ-CWD=TARGET-CWD",
        ],
    )

    assert requirement.exit_code == 0
    assert coverage.exit_code == 0
    assert projection.exit_code == 0
    assert map_path.is_file()


def test_cli_commands_match_real_help_at_the_leaf_command_level() -> None:
    runner = CliRunner()
    for path in _skill_paths():
        _, body = _parse_skill(path)
        commands = re.findall(r"`(quality-weaver [^`\n]+)`", body)
        assert commands, f"{path} must reference an exact CLI command"
        for command in commands:
            tokens = shlex.split(command)
            command_path = _command_path(tokens)
            arguments = tokens[1 + len(command_path) :]
            first_option = next(
                (index for index, token in enumerate(arguments) if token.startswith("--")),
                len(arguments),
            )
            assert first_option == POSITIONAL_COUNTS[command_path], command
            result = runner.invoke(app, [*command_path, "--help"])
            assert result.exit_code == 0, command
            assert f"root {' '.join(command_path)}" in result.stdout
            for option in (token for token in tokens if token.startswith("--")):
                assert option in result.stdout, f"{option} absent from leaf help for {command}"


def test_skills_delegate_state_projection_and_approval_to_the_cli_and_human() -> None:
    bodies = {path.parent.name: _parse_skill(path)[1] for path in _skill_paths()}

    for body in bodies.values():
        assert "Do not write `<project-path>/.quality-weaver/state.json`" in body
        assert "Do not approve a gate" in body
    coverage = bodies["plan-coverage"]
    assert "quality-weaver testmap render" in coverage
    assert "The Test Map is only the CLI-rendered projection" in coverage
    assert "Do not calculate Test Map values" in coverage


def test_analyze_uses_the_public_requirement_validator() -> None:
    body = _parse_skill(SKILLS_ROOT / "analyze-requirements" / "SKILL.md")[1]

    assert (
        "quality-weaver requirements validate "
        "<project-path>/.quality-weaver/normalized/requirements.yaml"
    ) in body
    assert "schema facility" not in body
    assert "public CLI has no" not in body


def test_plan_coverage_limits_cli_claims_to_deterministic_finding_codes() -> None:
    body = _parse_skill(SKILLS_ROOT / "plan-coverage" / "SKILL.md")[1]
    deterministic_codes = {
        "COVERAGE_CATALOG_VERSION_MISMATCH",
        "COVERAGE_DUPLICATE_KEY",
        "COVERAGE_DUPLICATE_ID",
        "COVERAGE_UNKNOWN_REQUIREMENT",
        "COVERAGE_UNKNOWN_TARGET",
        "COVERAGE_UNKNOWN_VIEWPOINT",
        "COVERAGE_EVIDENCE_REQUIRED",
        "COVERAGE_QUESTION_REQUIRED",
        "COVERAGE_UNRESOLVED",
    }

    assert deterministic_codes <= set(re.findall(r"`(COVERAGE_[A-Z_]+)`", body))
    assert "CLI detects missing high-risk coverage" not in body
    assert "Model proposal and human Gate 2 review" in body


def test_design_has_conditional_gate2_reopen_and_canonical_markdown_review() -> None:
    body = _parse_skill(SKILLS_ROOT / "design-testcases" / "SKILL.md")[1]

    assert "quality-weaver reopen coverage <project-path>" in body
    assert (
        "quality-weaver testcases validate "
        "<project-path>/.quality-weaver/coverage/ledger.yaml "
        "<project-path>/.quality-weaver/tests/outlines/test-outline.yaml "
        "<project-path>/.quality-weaver/tests/detailed/testcases.md"
    ) in body
    assert "canonical Markdown is the source of truth" in body
    approval = (
        "quality-weaver approve testcases <project-path> --artifact "
        "<project-path>/.quality-weaver/tests/detailed/testcases.md"
    )
    assert approval in body
    assert "quality-weaver regenerate testcases <project-path>" in body
    assert body.index("quality-weaver approve coverage <project-path>") < body.index(
        "quality-weaver regenerate testcases <project-path>"
    )
    assert "Gate 2" in body and "Gate 3" in body


def test_export_consumes_canonical_markdown_and_plugin_profile_root() -> None:
    body = _parse_skill(SKILLS_ROOT / "export-testcases" / "SKILL.md")[1]

    assert "<project-path>/.quality-weaver/tests/detailed/testcases.md" in body
    assert "--profiles-root <plugin-root>/profiles" in body
    assert "--workbook <workbook-kind>" in body
    assert "do not accept a filename policy from the user" in body
    assert "approved canonical Markdown" in body
    assert "YAML is the source of truth" not in body


def test_shared_skill_directories_contain_no_platform_metadata_or_readmes() -> None:
    unexpected = {
        path.relative_to(SKILLS_ROOT).as_posix()
        for path in SKILLS_ROOT.rglob("*")
        if path.is_file() and path.name != "SKILL.md"
    }
    assert unexpected == set()
