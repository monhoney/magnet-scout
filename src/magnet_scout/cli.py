from __future__ import annotations

import asyncio
import json
import logging
import os
import unicodedata
from pathlib import Path
from typing import Annotated

import httpx
import typer

from magnet_scout.cache import VerificationCache, cache_status, clear_cache
from magnet_scout.config import ConfigError, TorznabSettings, load_torznab_settings
from magnet_scout.dht import CompositeVerifier, DHTBatchVerifier, DHTUnavailable
from magnet_scout.models import SearchReport, TorrentResult
from magnet_scout.providers.registry import default_providers
from magnet_scout.providers.torznab import TorznabProvider
from magnet_scout.service import SearchService
from magnet_scout.verification import TrackerClient, TrackerVerifier, WebSeedVerifier

app = typer.Typer(no_args_is_help=True, help="Discover useful BitTorrent magnet metadata.")
cache_app = typer.Typer(no_args_is_help=True, help="Inspect or clear local caches.")
app.add_typer(cache_app, name="cache")
log = logging.getLogger("magnet_scout")


def _cache_root() -> Path:
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "magnet-scout"


@app.callback()
def main() -> None:
    """Discover and rank BitTorrent magnet metadata without downloading content."""


def _size(value: int | None) -> str:
    if value is None:
        return "unknown"
    size = float(value)
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024
    return "unknown"


def _human_result(index: int, result: TorrentResult) -> str:
    seeds = "unavailable" if result.reported_seeders is None else str(result.reported_seeders)
    peers = "not checked" if result.verified_peers is None else str(result.verified_peers)
    if result.verified_seeders is not None:
        verified_seeds = str(result.verified_seeders)
    elif result.verification_attempted:
        verified_seeds = "unavailable"
    else:
        verified_seeds = "not checked"
    dht_peers = "not checked" if result.dht_peers is None else str(result.dht_peers)
    file_count = "unknown" if result.file_count is None else str(result.file_count)
    lines = [
        f"[{index}] {_safe_text(result.title)}",
        f"    Size:              {_size(result.size_bytes)}",
        f"    Files:             {file_count}",
        f"    Reported seeders:  {seeds}",
        f"    Verified seeders:  {verified_seeds}",
        f"    Verified peers:    {peers}",
        f"    DHT peers:         {dht_peers}",
        f"    Verification:      {result.verification_status.value}",
        f"    Trackers:          {result.trackers_responded}/{result.trackers_checked} responded",
        f"    Web seeds:         {result.web_seeds_responded}/{result.web_seeds_checked} responded",
        f"    Providers:         {', '.join(result.providers)}",
        f"    Health:            {result.health.value}",
        f"    Confidence:        {result.confidence_score:.0f}%",
    ]
    if result.creators:
        lines.append(f"    Creators:          {_safe_text(', '.join(result.creators))}")
    if result.license_url:
        lines.append(f"    License:           {_safe_text(result.license_url)}")
    elif result.rights:
        lines.append(f"    Rights:            {_safe_text(result.rights)}")
    if result.description:
        lines.append(f"    Description:       {_safe_text(result.description[:300])}")
    if result.file_extensions:
        summary = ", ".join(f"{key}: {count}" for key, count in result.file_extensions.items())
        lines.append(f"    File types:        {_safe_text(summary)}")
    for path in result.sample_files[:5]:
        lines.append(f"    File:              {_safe_text(path)}")
    if result.metainfo_url:
        lines.append(f"    Torrent metadata:  {_safe_text(result.metainfo_url)}")
    lines.append(f"    Magnet URI:        {result.magnet_uri}")
    return "\n".join(lines)


def _safe_text(value: str) -> str:
    return "".join(
        character if not unicodedata.category(character).startswith("C") else " "
        for character in value
    )


async def _run_search(
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
    dht: bool,
    dht_timeout: float,
    torznab_settings: list[TorznabSettings],
    ia_subjects: list[str],
    ia_license_only: bool,
) -> SearchReport:
    limits = httpx.Limits(max_connections=10, max_keepalive_connections=5)
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(request_timeout),
        limits=limits,
        follow_redirects=False,
        trust_env=False,
    ) as client:
        cache_root = _cache_root()
        registry = default_providers(
            client,
            cache_root,
            internet_archive_subjects=tuple(ia_subjects),
            internet_archive_license_only=ia_license_only,
        )
        for setting in torznab_settings:
            provider = TorznabProvider(
                client,
                name=setting.name,
                url=setting.url,
                api_key=setting.api_key(),
            )
            registry[provider.name] = provider
        unknown = set(provider_names) - registry.keys()
        if unknown:
            raise typer.BadParameter(f"unknown provider(s): {', '.join(sorted(unknown))}")
        selected = (
            [registry[name] for name in provider_names]
            if provider_names
            else list(registry.values())
        )
        cache = (
            VerificationCache(cache_root / "verification.sqlite3", cache_ttl)
            if cache_ttl > 0
            else None
        )
        tracker_verifier = TrackerVerifier(
            TrackerClient(client, timeout=min(request_timeout, 10.0)),
            concurrency=10,
            cache=cache,
        )
        verifiers: list[object] = [tracker_verifier, WebSeedVerifier(client)]
        if dht:
            verifiers.append(DHTBatchVerifier(timeout=min(dht_timeout, total_timeout)))
        verifier = CompositeVerifier(verifiers)
        async with asyncio.timeout(total_timeout):
            return await SearchService(selected, verifier).search(
                query,
                top=top,
                min_seeders=min_seeders,
                min_reported_seeders=min_reported_seeders,
                min_verified_seeders=min_verified_seeders,
                verify=verify,
            )


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Search terms")],
    top: Annotated[int, typer.Option(min=1, max=100)] = 10,
    min_seeders: Annotated[
        int | None, typer.Option(min=0, help="Legacy: reported, or verified with --verify")
    ] = None,
    min_reported_seeders: Annotated[int | None, typer.Option(min=0)] = None,
    min_verified_seeders: Annotated[int | None, typer.Option(min=0)] = None,
    verify: Annotated[bool, typer.Option(help="Independently observe swarm availability")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Emit structured JSON")] = False,
    provider: Annotated[list[str] | None, typer.Option("--provider")] = None,
    timeout: Annotated[float, typer.Option(min=0.1, max=120)] = 10.0,
    cache_ttl: Annotated[
        int, typer.Option(min=0, max=86400, help="Verification cache seconds; 0 disables")
    ] = 300,
    total_timeout: Annotated[float, typer.Option(min=1, max=300)] = 30.0,
    dht: Annotated[
        bool, typer.Option(help="Also observe peers through isolated BEP 5 DHT")
    ] = False,
    dht_timeout: Annotated[float, typer.Option(min=3, max=60)] = 15.0,
    config: Annotated[Path | None, typer.Option(help="TOML configuration path")] = None,
    torznab_url: Annotated[str | None, typer.Option(help="One-off Torznab endpoint")] = None,
    torznab_name: Annotated[str, typer.Option(help="Name for --torznab-url")] = "default",
    ia_subject: Annotated[
        list[str] | None,
        typer.Option("--ia-subject", help="Require an Internet Archive subject; repeat for OR"),
    ] = None,
    ia_license_only: Annotated[
        bool,
        typer.Option(help="Require Internet Archive items with explicit license metadata"),
    ] = False,
) -> None:
    """Search configured metadata providers."""
    if min_verified_seeders is not None and not verify:
        raise typer.BadParameter("--min-verified-seeders requires --verify")
    if dht and not verify:
        raise typer.BadParameter("--dht requires --verify")
    config_root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    config_path = config or config_root / "magnet-scout" / "config.toml"
    try:
        settings = load_torznab_settings(config_path, required=config is not None)
        if torznab_url:
            settings.append(
                TorznabSettings(
                    torznab_name,
                    torznab_url,
                    "MAGNET_SCOUT_TORZNAB_API_KEY"
                    if os.environ.get("MAGNET_SCOUT_TORZNAB_API_KEY")
                    else None,
                )
            )
    except ConfigError as exc:
        raise typer.BadParameter(str(exc)) from None
    try:
        report = asyncio.run(
            _run_search(
                query,
                top,
                min_seeders,
                min_reported_seeders,
                min_verified_seeders,
                provider or [],
                timeout,
                verify,
                cache_ttl,
                total_timeout,
                dht,
                dht_timeout,
                settings,
                ia_subject or [],
                ia_license_only,
            )
        )
    except TimeoutError:
        typer.echo(f"search exceeded the {total_timeout:g}s total timeout", err=True)
        raise typer.Exit(1) from None
    except DHTUnavailable as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None
    if json_output:
        typer.echo(
            json.dumps(
                {
                    "query": report.query,
                    "results": [result.to_dict() for result in report.results],
                    "failures": [
                        {
                            "provider": failure.provider,
                            "kind": failure.kind,
                            "message": failure.message,
                        }
                        for failure in report.failures
                    ],
                },
                indent=2,
            )
        )
    else:
        for index, result in enumerate(report.results, 1):
            typer.echo(_human_result(index, result))
        for failure in report.failures:
            typer.echo(f"{failure.provider} {failure.kind}: {failure.message}", err=True)
    if not report.results and report.failures:
        raise typer.Exit(1)


@cache_app.command("status")
def cache_status_command(
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Show aggregate cache information without exposing cached query data."""
    status = cache_status(_cache_root())
    if json_output:
        typer.echo(json.dumps(status, indent=2))
        return
    typer.echo(f"Location:             {status['root']}")
    typer.echo(f"Files:                {status['files']}")
    typer.echo(f"Size:                 {_size(status['size_bytes'])}")
    typer.echo(f"Verification entries: {status['verification_entries']}")
    typer.echo(
        f"Academic index:       {'cached' if status['academic_index_cached'] else 'missing'}"
    )


@cache_app.command("clear")
def cache_clear_command(
    yes: Annotated[bool, typer.Option("--yes", help="Confirm deletion")] = False,
) -> None:
    """Delete MagnetScout's known cache files."""
    if not yes:
        raise typer.BadParameter("cache clear requires --yes")
    removed = clear_cache(_cache_root())
    typer.echo(f"Removed {len(removed)} cache file(s).")
