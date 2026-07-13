from typer.testing import CliRunner

from quality_weaver.cli import app


def test_version_command() -> None:
    result = CliRunner().invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "quality-weaver 0.1.0"
