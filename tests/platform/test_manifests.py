import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CODEX_MANIFEST = PROJECT_ROOT / ".codex-plugin" / "plugin.json"
CLAUDE_MANIFEST = PROJECT_ROOT / ".claude-plugin" / "plugin.json"
EXPECTED_CAPABILITIES = {
    "initialize",
    "analyze-requirements",
    "plan-coverage",
    "design-testcases",
    "export-testcases",
    "status",
}


def _load(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def test_both_manifests_have_same_identity_and_version() -> None:
    codex = _load(CODEX_MANIFEST)
    claude = _load(CLAUDE_MANIFEST)

    assert codex["name"] == claude["name"] == "quality-weaver"
    assert codex["version"] == claude["version"] == "0.1.0"
    assert codex["description"] == claude["description"]


def test_manifests_expose_the_same_shared_skill_capabilities() -> None:
    codex = _load(CODEX_MANIFEST)
    _load(CLAUDE_MANIFEST)
    actual_skills = {path.parent.name for path in (PROJECT_ROOT / "skills").glob("*/SKILL.md")}

    assert codex["skills"] == "./skills/"
    assert actual_skills == EXPECTED_CAPABILITIES
    assert set(codex["interface"]["capabilities"]) == actual_skills


def test_codex_manifest_has_current_required_publisher_and_interface_fields() -> None:
    codex = _load(CODEX_MANIFEST)

    assert codex["author"]["name"] == "QualityWeaver"
    assert codex["interface"] == {
        "displayName": "QualityWeaver",
        "shortDescription": "Viewpoint-driven manual test design",
        "longDescription": (
            "Design traceable manual tests from Markdown requirements with deterministic "
            "validation and three human approval gates."
        ),
        "developerName": "QualityWeaver",
        "category": "Productivity",
        "defaultPrompt": ["Show the QualityWeaver status for this project."],
        "capabilities": sorted(EXPECTED_CAPABILITIES),
    }


def test_claude_manifest_uses_only_portable_identity_and_discovery_fields() -> None:
    claude = _load(CLAUDE_MANIFEST)

    assert set(claude) == {"name", "version", "description", "author"}
    assert claude["author"]["name"] == "QualityWeaver"


@pytest.mark.skipif(shutil.which("claude") is None, reason="Claude CLI is not installed")
def test_real_claude_validator_and_component_discovery() -> None:
    validated = subprocess.run(
        ["claude", "plugin", "validate", "."],
        cwd=PROJECT_ROOT,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    details = subprocess.run(
        ["claude", "--plugin-dir", ".", "plugin", "details", "quality-weaver"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    output = validated.stdout + validated.stderr
    assert validated.returncode == 0, output
    known_warning = "CLAUDE.md at the plugin root is not loaded as project context"
    unexpected_warnings = [
        line
        for line in output.splitlines()
        if ("warning" in line.lower() or "❯" in line)
        and known_warning not in line
        and "found 1 warning" not in line.lower()
        and "validation passed with warnings" not in line.lower()
    ]
    assert not unexpected_warnings, output
    assert details.returncode == 0, details.stdout + details.stderr
    inventory = details.stdout + details.stderr
    assert "Skills (6)" in inventory
    for skill_name in EXPECTED_CAPABILITIES:
        assert skill_name in inventory
