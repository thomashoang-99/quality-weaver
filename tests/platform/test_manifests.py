import json
from pathlib import Path
from typing import Any

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

    assert set(claude) == {"name", "version", "description"}
