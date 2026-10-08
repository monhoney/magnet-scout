from typing import Any

import httpx
import pytest

from magnet_scout.providers import fedora
from magnet_scout.providers.fedora import FedoraProvider

HASH = "0123456789abcdef0123456789abcdef01234567"


@pytest.mark.asyncio
async def test_searches_official_catalog_and_normalizes_torrent(monkeypatch: Any) -> None:
    class FakeTorrent:
        size = 2_000_000_000

        def magnet(self) -> str:
            return f"magnet:?xt=urn:btih:{HASH}&tr=https%3A%2F%2Ftracker.fedoraproject.org"

    monkeypatch.setattr(fedora.Torrent, "read_stream", lambda stream, validate: FakeTorrent())

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/torrents/":
            return httpx.Response(
                200,
                text=(
                    '<a href="Fedora-Workstation-Live-x86_64-44.torrent">workstation</a>'
                    '<a href="Fedora-Server-dvd-x86_64-44.torrent">server</a>'
                ),
            )
        assert request.url.path.endswith("Fedora-Workstation-Live-x86_64-44.torrent")
        return httpx.Response(200, content=b"small metainfo")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        results = await FedoraProvider(client).search("fedora workstation", 10)

    assert len(results) == 1
    assert results[0].title == "Fedora-Workstation-Live-x86_64-44"
    assert results[0].info_hash == HASH
    assert results[0].size_bytes == 2_000_000_000
    assert results[0].providers == ["fedora"]
    assert results[0].reported_seeders is None
    assert results[0].provider_urls[0].endswith(".torrent")


@pytest.mark.asyncio
async def test_skips_malformed_torrent_without_failing_other_results(monkeypatch: Any) -> None:
    class FakeTorrent:
        size = 1

        def magnet(self) -> str:
            return f"magnet:?xt=urn:btih:{HASH}"

    def read_stream(stream: Any, validate: bool) -> FakeTorrent:
        if stream.read() == b"bad":
            raise ValueError("malformed")
        return FakeTorrent()

    monkeypatch.setattr(fedora.Torrent, "read_stream", read_stream)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/torrents/":
            return httpx.Response(
                200,
                text='<a href="Fedora-Bad.torrent">bad</a><a href="Fedora-Good.torrent">good</a>',
            )
        return httpx.Response(200, content=b"bad" if "Bad" in request.url.path else b"good")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        results = await FedoraProvider(client).search("fedora", 10)

    assert [result.title for result in results] == ["Fedora-Good"]


@pytest.mark.asyncio
async def test_rejects_oversized_catalog() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"x" * 11))
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(ValueError, match="catalog exceeds"):
            await FedoraProvider(client, max_index_bytes=10).search("fedora", 1)
