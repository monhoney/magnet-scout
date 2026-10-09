import hashlib

import httpx
import pytest

from magnet_scout.providers.fedora import FedoraProvider
from tests._bencode import encode

HASH = "0123456789abcdef0123456789abcdef01234567"


@pytest.mark.asyncio
async def test_searches_official_catalog_and_normalizes_torrent() -> None:
    info = {
        b"length": 2_000_000_000,
        b"name": b"Fedora-Workstation.iso",
        b"piece length": 16384,
        b"pieces": b"x" * 20,
    }
    torrent_bytes = encode({b"announce": b"https://tracker.fedoraproject.org", b"info": info})
    expected_hash = hashlib.sha1(encode(info), usedforsecurity=False).hexdigest()

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
        return httpx.Response(200, content=torrent_bytes)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        results = await FedoraProvider(client).search("fedora workstation", 10)

    assert len(results) == 1
    assert results[0].title == "Fedora-Workstation-Live-x86_64-44"
    assert results[0].info_hash == expected_hash
    assert results[0].size_bytes == 2_000_000_000
    assert results[0].providers == ["fedora"]
    assert results[0].reported_seeders is None
    assert results[0].provider_urls[0].endswith(".torrent")


@pytest.mark.asyncio
async def test_skips_malformed_torrent_without_failing_other_results() -> None:
    good = encode(
        {
            b"info": {
                b"length": 1,
                b"name": b"good.iso",
                b"piece length": 16384,
                b"pieces": b"x" * 20,
            }
        }
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/torrents/":
            return httpx.Response(
                200,
                text='<a href="Fedora-Bad.torrent">bad</a><a href="Fedora-Good.torrent">good</a>',
            )
        return httpx.Response(200, content=b"bad" if "Bad" in request.url.path else good)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        results = await FedoraProvider(client).search("fedora", 10)

    assert [result.title for result in results] == ["Fedora-Good"]


@pytest.mark.asyncio
async def test_rejects_oversized_catalog() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"x" * 11))
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(ValueError, match="catalog exceeds"):
            await FedoraProvider(client, max_index_bytes=10).search("fedora", 1)
