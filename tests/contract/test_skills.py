import re
import shlex
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

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
    ("export",),
    ("coverage", "validate"),
    ("testmap", "render"),
    ("outline", "validate"),
    ("testcases", "validate"),
    ("testcases", "render"),
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
    assert "Do not write `.quality-weaver/state.json`" in body
    assert "Do not approve a gate" in body
    assert all(token not in body for token in PORTABILITY_VIOLATIONS)


def test_declared_read_paths_are_portable_templates_or_repository_paths() -> None:
    allowed_roots = {
        "<project-path>",
        "<requirements-glob>",
        "<profiles-root>",
        ".quality-weaver/",
        "profiles/",
        "schemas/",
        "viewpoints/",
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
            if value.startswith(("profiles/", "schemas/", "viewpoints/")):
                static_prefix = value.split("*", 1)[0].rstrip("/")
                assert (PROJECT_ROOT / static_prefix).exists(), value


def test_cli_commands_match_real_help_at_the_leaf_command_level() -> None:
    runner = CliRunner()
    for path in _skill_paths():
        _, body = _parse_skill(path)
        commands = re.findall(r"`(quality-weaver [^`\n]+)`", body)
        assert commands, f"{path} must reference an exact CLI command"
        for command in commands:
            tokens = shlex.split(command)
            command_path = _command_path(tokens)
            result = runner.invoke(app, [*command_path, "--help"])
            assert result.exit_code == 0, command
            assert f"root {' '.join(command_path)}" in result.stdout
            for option in (token for token in tokens if token.startswith("--")):
                assert option in result.stdout, f"{option} absent from leaf help for {command}"


def test_skills_delegate_state_projection_and_approval_to_the_cli_and_human() -> None:
    bodies = {path.parent.name: _parse_skill(path)[1] for path in _skill_paths()}

    for body in bodies.values():
        assert "Do not write `.quality-weaver/state.json`" in body
        assert "Do not approve a gate" in body
    coverage = bodies["plan-coverage"]
    assert "quality-weaver testmap render" in coverage
    assert "The Test Map is only the CLI-rendered projection" in coverage
    assert "Do not calculate Test Map values" in coverage


def test_shared_skill_directories_contain_no_platform_metadata_or_readmes() -> None:
    unexpected = {
        path.relative_to(SKILLS_ROOT).as_posix()
        for path in SKILLS_ROOT.rglob("*")
        if path.is_file() and path.name != "SKILL.md"
    }
    assert unexpected == set()
