from pathlib import Path

import pytest
from click import unstyle
from typer.testing import CliRunner

from magnet_scout.cli import app

runner = CliRunner()


def _all_output(result: object) -> str:
    output = str(getattr(result, "output", "")) + str(getattr(result, "stderr", ""))
    return " ".join(unstyle(output).split())


def test_cache_status_and_confirmed_clear(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "magnet-scout"
    root.mkdir()
    (root / "academic-torrents.xml").write_bytes(b"index")
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

    status = runner.invoke(app, ["cache", "status", "--json"])
    assert status.exit_code == 0
    assert '"academic_index_cached": true' in status.output

    refused = runner.invoke(app, ["cache", "clear"])
    assert refused.exit_code != 0
    assert "requires --yes" in _all_output(refused)

    cleared = runner.invoke(app, ["cache", "clear", "--yes"])
    assert cleared.exit_code == 0
    assert "Removed 1 cache file" in cleared.output
    assert not (root / "academic-torrents.xml").exists()
