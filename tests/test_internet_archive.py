import hashlib

import httpx
import pytest

from magnet_scout.providers.internet_archive import InternetArchiveProvider
from tests._bencode import encode

HASH = "0123456789abcdef0123456789abcdef01234567"


async def test_search_builds_result_from_structured_metadata() -> None:
    info = {
        b"length": 1234,
        b"name": b"public-linux.img",
        b"piece length": 16384,
        b"pieces": b"x" * 20,
    }
    torrent_bytes = encode(
        {
            b"announce": b"https://tracker.test/a",
            b"info": info,
            b"url-list": b"https://archive.test/download/",
        }
    )
    expected_hash = hashlib.sha1(encode(info), usedforsecurity=False).hexdigest()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/advancedsearch.php":
            return httpx.Response(
                200,
                json={
                    "response": {
                        "docs": [{"identifier": "public-linux", "title": "Public Linux Image"}]
                    }
                },
            )
        if request.url.path == "/metadata/public-linux":
            return httpx.Response(
                200,
                json={
                    "metadata": {
                        "title": "Public Linux Image",
                        "description": "A public image",
                        "creator": ["Example Foundation"],
                        "licenseurl": "https://creativecommons.org/licenses/by/4.0/",
                    },
                    "files": [
                        {
                            "name": "public-linux_archive.torrent",
                            "format": "Archive BitTorrent",
                        }
                    ],
                },
            )
        if request.url.path == "/download/public-linux/public-linux_archive.torrent":
            return httpx.Response(200, content=torrent_bytes)
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        results = await InternetArchiveProvider(client).search("linux", 5)

    assert len(results) == 1
    assert results[0].info_hash == expected_hash
    assert results[0].providers == ["internet-archive"]
    assert results[0].size_bytes == 1234
    assert results[0].reported_seeders is None
    assert "xt=urn:btih:" in results[0].magnet_uri
    assert "&ws=" in results[0].magnet_uri
    assert results[0].web_seeds == ["https://archive.test/download/"]
    assert results[0].description == "A public image"
    assert results[0].creators == ["Example Foundation"]
    assert results[0].license_url == "https://creativecommons.org/licenses/by/4.0/"
    assert results[0].metainfo_url is not None


async def test_subject_and_license_filters_are_sent_to_advanced_search() -> None:
    query = ""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal query
        query = request.url.params["q"]
        return httpx.Response(200, json={"response": {"docs": []}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = InternetArchiveProvider(
            client,
            subjects=("travel", "nature"),
            license_only=True,
        )
        await provider.search("VR180 beach", 5)

    assert 'title:("VR180")' in query
    assert 'subject:("beach")' in query
    assert '(subject:("travel") OR subject:("nature"))' in query
    assert "licenseurl:*" in query


async def test_rejects_oversized_search_response() -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(200, content=b"x" * 11))
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(ValueError, match="safety limit"):
            await InternetArchiveProvider(client, max_search_bytes=10).search("linux", 1)
