import asyncio
from pathlib import Path

import pytest
from click import unstyle
from typer.testing import CliRunner

from magnet_scout import cli
from magnet_scout.cli import app
from magnet_scout.config import TorznabSettings
from magnet_scout.models import SearchReport, TorrentResult, VerificationStatus

runner = CliRunner()


def _all_output(result: object) -> str:
    output = str(getattr(result, "output", "")) + str(getattr(result, "stderr", ""))
    return " ".join(unstyle(output).split())


def test_verify_is_forwarded_to_search(monkeypatch: object) -> None:
    seen: dict[str, bool] = {}

    async def fake_run_search(
        query: str,
        top: int,
        min_seeders: int | None,
        min_reported_seeders: int | None,
        min_verified_seeders: int | None,
        provider_names: list[str],
        request_timeout: float,
        verify: bool,
        cache_ttl: int,
        total_timeout: float,
        torznab_settings: list[TorznabSettings],
        ia_subjects: list[str],
        ia_license_only: bool,
    ) -> SearchReport:
        seen["verify"] = verify
        seen["ia_license_only"] = ia_license_only
        return SearchReport(query, [])

    monkeypatch.setattr(cli, "_run_search", fake_run_search)  # type: ignore[attr-defined]
    result = runner.invoke(app, ["search", "ubuntu", "--verify"])
    assert result.exit_code == 0
    assert seen == {"verify": True, "ia_license_only": True}


def test_unlicensed_internet_archive_results_require_opt_in(monkeypatch: object) -> None:
    seen: dict[str, bool] = {}

    async def fake_run_search(*args: object, **kwargs: object) -> SearchReport:
        seen["ia_license_only"] = bool(args[-1])
        return SearchReport("ubuntu", [])

    monkeypatch.setattr(cli, "_run_search", fake_run_search)  # type: ignore[attr-defined]
    result = runner.invoke(app, ["search", "ubuntu", "--include-unlicensed-ia"])
    assert result.exit_code == 0
    assert seen == {"ia_license_only": False}


def test_verified_seed_filter_requires_verification() -> None:
    result = runner.invoke(app, ["search", "ubuntu", "--min-verified-seeders", "5"])
    assert result.exit_code != 0
    assert "requires --verify" in _all_output(result)


def test_missing_explicit_config_is_rejected(tmp_path: Path) -> None:
    result = runner.invoke(app, ["search", "ubuntu", "--config", str(tmp_path / "missing")])
    assert result.exit_code != 0
    assert "does not exist" in result.output


def test_unknown_provider() -> None:
    result = runner.invoke(app, ["search", "ubuntu", "--provider", "missing"])
    assert result.exit_code != 0
    assert "unknown provider" in result.output


def test_human_output_labels_magnet_and_seeder_sources() -> None:
    item = TorrentResult(
        title="Public dataset",
        magnet_uri="magnet:?xt=urn:btih:" + "a" * 40,
        info_hash="a" * 40,
        reported_seeders=12,
        verified_seeders=4,
    )

    output = cli._human_result(1, item)

    assert "Reported seeders:  12" in output
    assert "Verified seeders:  4" in output
    assert "Magnet URI:        magnet:?xt=urn:btih:" in output


def test_human_output_distinguishes_unavailable_verified_seeders() -> None:
    item = TorrentResult(
        title="Public dataset",
        magnet_uri="magnet:?xt=urn:btih:" + "a" * 40,
        info_hash="a" * 40,
        verification_attempted=True,
        verification_status=VerificationStatus.UNREACHABLE,
    )

    output = cli._human_result(1, item)

    assert "Reported seeders:  unavailable" in output
    assert "Verified seeders:  unavailable" in output


def test_total_timeout_stops_slow_provider(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class SlowProvider:
        name = "slow"

        async def search(self, query: str, limit: int) -> list[object]:
            await asyncio.sleep(2)
            return []

    monkeypatch.setattr(
        cli, "default_providers", lambda client, root, **kwargs: {"slow": SlowProvider()}
    )
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    result = runner.invoke(app, ["search", "ubuntu", "--provider", "slow", "--total-timeout", "1"])
    assert result.exit_code == 1
    assert "exceeded the 1s total timeout" in result.output
