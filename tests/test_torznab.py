import httpx
import pytest

from magnet_scout.network import ResponseTooLarge
from magnet_scout.providers.torznab import TorznabError, TorznabProvider

HASH = "0123456789abcdef0123456789abcdef01234567"
FEED = f"""<?xml version="1.0"?>
<rss xmlns:torznab="http://torznab.com/schemas/2015/feed"><channel><item>
  <title>Legal Linux Image</title>
  <guid>https://index.test/details/1</guid>
  <enclosure url="magnet:?xt=urn:btih:{HASH}" length="1048576" />
  <torznab:attr name="infohash" value="{HASH}" />
  <torznab:attr name="seeders" value="12" />
  <torznab:attr name="peers" value="17" />
</item></channel></rss>""".encode()


async def test_normalizes_torznab_feed_without_trusting_seeders() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["t"] == "search"
        assert request.url.params["q"] == "linux"
        assert request.url.params["apikey"] == "hidden"
        return httpx.Response(200, content=FEED)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        results = await TorznabProvider(
            client, name="legal", url="https://index.test/api", api_key="hidden"
        ).search("linux", 10)

    assert len(results) == 1
    assert results[0].info_hash == HASH
    assert results[0].reported_seeders == 12
    assert results[0].reported_leechers == 5
    assert results[0].verified is False
    assert results[0].providers == ["torznab:legal"]


async def test_infohash_can_build_magnet_when_feed_has_no_magnet() -> None:
    feed = f"""<rss xmlns:torznab="http://torznab.com/schemas/2015/feed"><channel><item>
      <title>Dataset</title><torznab:attr name="infohash" value="{HASH}" />
    </item></channel></rss>""".encode()
    transport = httpx.MockTransport(lambda _: httpx.Response(200, content=feed))
    async with httpx.AsyncClient(transport=transport) as client:
        results = await TorznabProvider(client, name="test", url="https://index.test/api").search(
            "data", 1
        )
    assert results[0].magnet_uri.startswith("magnet:?xt=urn:btih:")


async def test_rejects_xml_entities() -> None:
    feed = (
        b'<!DOCTYPE rss [<!ENTITY x "expanded">]><rss><channel><title>&x;</title></channel></rss>'
    )
    transport = httpx.MockTransport(lambda _: httpx.Response(200, content=feed))
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(TorznabError, match="malformed XML"):
            await TorznabProvider(client, name="test", url="https://index.test/api").search(
                "data", 1
            )


async def test_rejects_oversized_feed() -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(200, content=b"x" * 11))
    async with httpx.AsyncClient(transport=transport) as client:
        provider = TorznabProvider(
            client, name="test", url="https://index.test/api", max_response_bytes=10
        )
        with pytest.raises(ResponseTooLarge):
            await provider.search("data", 1)


async def test_api_key_requires_https() -> None:
    async with httpx.AsyncClient() as client:
        with pytest.raises(ValueError, match="HTTPS"):
            TorznabProvider(client, name="test", url="http://index.test/api", api_key="secret")
