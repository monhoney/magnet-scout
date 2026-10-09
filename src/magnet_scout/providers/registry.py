from __future__ import annotations

from pathlib import Path

import httpx

from magnet_scout.providers.academic_torrents import AcademicTorrentsProvider
from magnet_scout.providers.base import SearchProvider
from magnet_scout.providers.fedora import FedoraProvider
from magnet_scout.providers.internet_archive import InternetArchiveProvider


def default_providers(
    client: httpx.AsyncClient,
    cache_root: Path | None = None,
    *,
    internet_archive_subjects: tuple[str, ...] = (),
    internet_archive_license_only: bool = True,
) -> dict[str, SearchProvider]:
    root = cache_root or Path.home() / ".cache" / "magnet-scout"
    providers: list[SearchProvider] = [
        InternetArchiveProvider(
            client,
            subjects=internet_archive_subjects,
            license_only=internet_archive_license_only,
        ),
        AcademicTorrentsProvider(client, root / "academic-torrents.xml"),
        FedoraProvider(client),
    ]
    return {provider.name: provider for provider in providers}
