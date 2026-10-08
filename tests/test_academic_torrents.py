import json
import os
import time
from pathlib import Path

import httpx
import pytest
from defusedxml.common import EntitiesForbidden

from magnet_scout.providers.academic_torrents import AcademicTorrentsProvider

INDEX = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title>Open Machine Learning Dataset</title>
    <category>Dataset</category>
    <infohash>0123456789abcdef0123456789abcdef01234567</infohash>
    <link>https://academictorrents.com/details/0123456789abcdef0123456789abcdef01234567</link>
    <description>A public benchmark for machine learning research.</description>
    <size>123456</size>
  </item>
  <item><title>Malformed hash entry</title><infohash>not-a-hash</infohash></item>
</channel></rss>"""


async def test_searches_official_index_and_builds_magnet(tmp_path: Path) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.url == "https://academictorrents.com/database.xml"
        return httpx.Response(200, content=INDEX)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = AcademicTorrentsProvider(client, tmp_path / "index.xml")
        first = await provider.search("machine learning", 10)
        second = await provider.search("machine learning", 10)

    assert calls == 1
    assert len(first) == len(second) == 1
    assert first[0].providers == ["academic-torrents"]
    assert first[0].size_bytes == 123456
    assert first[0].info_hash == "0123456789abcdef0123456789abcdef01234567"
    assert first[0].trackers == ["http://academictorrents.com/announce.php"]


async def test_query_requires_all_terms(tmp_path: Path) -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(200))
    async with httpx.AsyncClient(transport=transport) as client:
        cache = tmp_path / "index.xml"
        cache.write_bytes(INDEX)
        results = await AcademicTorrentsProvider(client, cache).search("machine astronomy", 10)
    assert results == []


async def test_stale_index_is_used_when_refresh_fails(tmp_path: Path) -> None:
    cache = tmp_path / "index.xml"
    cache.write_bytes(INDEX)
    old = time.time() - 90000
    os.utime(cache, (old, old))
    transport = httpx.MockTransport(lambda _: httpx.Response(503))
    async with httpx.AsyncClient(transport=transport) as client:
        results = await AcademicTorrentsProvider(client, cache).search("machine learning", 10)
    assert len(results) == 1


async def test_stale_index_uses_conditional_request(tmp_path: Path) -> None:
    cache = tmp_path / "index.xml"
    cache.write_bytes(INDEX)
    cache.with_suffix(".meta.json").write_text(
        json.dumps({"etag": 'W/"abc"', "last_modified": "yesterday"})
    )
    old = time.time() - 90000
    os.utime(cache, (old, old))

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["if-none-match"] == 'W/"abc"'
        assert request.headers["if-modified-since"] == "yesterday"
        return httpx.Response(304)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        results = await AcademicTorrentsProvider(client, cache).search("machine learning", 10)
    assert len(results) == 1
    assert cache.stat().st_mtime > old


async def test_rejects_xml_entities(tmp_path: Path) -> None:
    malicious = (
        b'<!DOCTYPE rss [<!ENTITY x "expanded">]><rss><channel><title>&x;</title></channel></rss>'
    )
    transport = httpx.MockTransport(lambda _: httpx.Response(200, content=malicious))
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(EntitiesForbidden):
            await AcademicTorrentsProvider(client, tmp_path / "index.xml").search("x", 1)


async def test_oversized_refresh_uses_safe_stale_index(tmp_path: Path) -> None:
    cache = tmp_path / "index.xml"
    cache.write_bytes(INDEX)
    old = time.time() - 90000
    os.utime(cache, (old, old))
    transport = httpx.MockTransport(lambda _: httpx.Response(200, content=b"x" * (len(INDEX) + 1)))
    async with httpx.AsyncClient(transport=transport) as client:
        provider = AcademicTorrentsProvider(client, cache, max_index_bytes=len(INDEX))
        results = await provider.search("machine learning", 10)
    assert len(results) == 1
