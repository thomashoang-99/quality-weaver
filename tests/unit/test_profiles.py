import shutil
from pathlib import Path

import pytest

from quality_weaver.profiles import Profile, ProfileError

PROFILES_ROOT = Path("profiles")


def copy_profile(name: str, destination: Path) -> Path:
    profiles_root = destination / "profiles"
    shutil.copytree(PROFILES_ROOT / name, profiles_root / name)
    return profiles_root


def test_builtin_profiles_are_strict_and_keep_organization_metadata_out_of_core() -> None:
    generic = Profile.load("generic", PROFILES_ROOT)
    legacy = Profile.load("company-legacy", PROFILES_ROOT)

    assert generic.formats == ("markdown",)
    assert generic.organization is None
    assert legacy.formats == ("markdown", "excel")
    assert legacy.organization is not None
    assert legacy.organization.project_cell == "C1"
    assert set(legacy.workbooks) == {"it", "ut"}
    assert legacy.workbooks["ut"].template_path(legacy.root).is_file()


def test_unknown_profile_fails_with_typed_deterministic_error(tmp_path: Path) -> None:
    with pytest.raises(ProfileError) as raised:
        Profile.load("missing", tmp_path)

    assert raised.value.code == "PROFILE_UNKNOWN"
    assert str(raised.value) == "PROFILE_UNKNOWN: unknown profile: missing"


def test_profile_name_cannot_escape_explicit_profiles_root(tmp_path: Path) -> None:
    profiles_root = tmp_path / "profiles"
    profiles_root.mkdir()
    escaped = tmp_path / "escape"
    escaped.mkdir()
    (escaped / "profile.yaml").write_text(
        "schema_version: 1\nname: escape\nformats: [markdown]\n",
        encoding="utf-8",
    )

    with pytest.raises(ProfileError) as raised:
        Profile.load("../escape", profiles_root)

    assert raised.value.code == "PROFILE_UNKNOWN"


@pytest.mark.parametrize(
    "profile_yaml, code",
    [
        ("schema_version: 1\nname: bad\nformats: [pdf]\n", "PROFILE_SCHEMA_INVALID"),
        (
            "schema_version: 1\nname: bad\nformats: [markdown]\nunexpected: true\n",
            "PROFILE_SCHEMA_INVALID",
        ),
        (
            "schema_version: 1\nname: other\nformats: [markdown]\n",
            "PROFILE_NAME_MISMATCH",
        ),
    ],
)
def test_invalid_profile_schema_or_identity_is_rejected(
    tmp_path: Path, profile_yaml: str, code: str
) -> None:
    profile_dir = tmp_path / "bad"
    profile_dir.mkdir()
    (profile_dir / "profile.yaml").write_text(profile_yaml, encoding="utf-8")

    with pytest.raises(ProfileError) as raised:
        Profile.load("bad", tmp_path)

    assert raised.value.code == code


def test_profile_rejects_escaping_template_path(tmp_path: Path) -> None:
    profile_dir = tmp_path / "bad"
    profile_dir.mkdir()
    (profile_dir / "profile.yaml").write_text(
        """schema_version: 1
name: bad
formats: [excel]
workbooks:
  ut:
    template: ../outside.xlsx
    required_sheets: [Testcase]
    sheet: Testcase
    header_row: 12
    first_row: 16
    columns:
      id: 1
      title: 2
      traceability: 4
      preconditions: 7
      steps: 9
      expected: 10
    headers:
      id: Test case ID
      title: Item Test
      traceability: Description
      preconditions: Pre-conditions
      steps: Step
      expected: Expected Results
    filename: '{project}_{artifact}.xlsx'
""",
        encoding="utf-8",
    )

    with pytest.raises(ProfileError) as raised:
        Profile.load("bad", tmp_path)

    assert raised.value.code == "PROFILE_TEMPLATE_ESCAPE"


@pytest.mark.parametrize(
    "filename",
    [
        "{project.__class__}_{artifact}.xlsx",
        "{project[0]}_{artifact}.xlsx",
        "{project!r}_{artifact}.xlsx",
        "{project:>10}_{artifact}.xlsx",
        "{project}_{artifact}_{unknown}.xlsx",
        "{project}_{artifact.xlsx",
    ],
)
def test_profile_filename_policy_allows_only_plain_project_and_artifact_fields(
    tmp_path: Path, filename: str
) -> None:
    profiles_root = copy_profile("company-legacy", tmp_path)
    profile_path = profiles_root / "company-legacy" / "profile.yaml"
    content = profile_path.read_text(encoding="utf-8").replace(
        'filename: "{project}_{artifact}_Test Case UT.xlsx"',
        f'filename: "{filename}"',
        1,
    )
    profile_path.write_text(content, encoding="utf-8")

    with pytest.raises(ProfileError) as raised:
        Profile.load("company-legacy", profiles_root)

    assert raised.value.code == "PROFILE_SCHEMA_INVALID"


def test_profile_yaml_symlink_cannot_escape_resolved_profile_root(
    tmp_path: Path, monkeypatch
) -> None:
    profiles_root = tmp_path / "profiles"
    profile_root = profiles_root / "linked"
    profile_root.mkdir(parents=True)
    outside = tmp_path / "outside-profile.yaml"
    outside.write_text(
        "schema_version: 1\nname: linked\nformats: [markdown]\n",
        encoding="utf-8",
    )
    profile_path = profile_root / "profile.yaml"
    profile_path.write_text(outside.read_text(encoding="utf-8"), encoding="utf-8")
    original_resolve = Path.resolve

    def resolve_profile_link(path: Path, *args, **kwargs) -> Path:
        if path == profile_path:
            return outside
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve_profile_link)

    with pytest.raises(ProfileError) as raised:
        Profile.load("linked", profiles_root)

    assert raised.value.code == "PROFILE_FILE_ESCAPE"
