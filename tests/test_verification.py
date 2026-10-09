import asyncio
import struct
from pathlib import Path

import httpx
import pytest

from magnet_scout.cache import VerificationCache
from magnet_scout.models import TorrentResult, VerificationStatus
from magnet_scout.verification import (
    TrackerClient,
    TrackerError,
    TrackerObservation,
    TrackerVerifier,
    WebSeedVerifier,
    _http_scrape_url,
    _parse_udp_connect,
    _parse_udp_scrape,
)
from tests._bencode import encode

HASH = "0123456789abcdef0123456789abcdef01234567"


async def test_web_seed_verifier_uses_head_without_payload() -> None:
    methods: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        return httpx.Response(200)

    result = TorrentResult(
        "Public video",
        f"magnet:?xt=urn:btih:{HASH}",
        HASH,
        web_seeds=["https://archive.test/download/"],
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        verifier = WebSeedVerifier(http, allow_private_addresses=True)
        await verifier.verify_many([result])

    assert methods == ["HEAD"]
    assert result.web_seeds_checked == 1
    assert result.web_seeds_responded == 1
    assert result.web_seed_responsive is True
    assert result.verified_seeders is None


async def test_web_seed_failure_is_not_swarm_evidence() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(503))
    result = TorrentResult(
        "Public video",
        f"magnet:?xt=urn:btih:{HASH}",
        HASH,
        web_seeds=["https://archive.test/download/"],
    )
    async with httpx.AsyncClient(transport=transport) as http:
        await WebSeedVerifier(http, allow_private_addresses=True).verify_many([result])

    assert result.web_seed_responsive is False
    assert result.verified is False


async def test_http_scrape_reads_seeders_without_announcing() -> None:
    raw_hash = bytes.fromhex(HASH)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/scrape"
        assert b"info_hash=" in request.url.query
        return httpx.Response(
            200,
            content=encode(
                {
                    b"files": {
                        raw_hash: {
                            b"complete": 12,
                            b"incomplete": 4,
                            b"downloaded": 30,
                        }
                    }
                }
            ),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = TrackerClient(http, allow_private_addresses=True)
        observation = await client.scrape("http://tracker.test/announce", HASH)

    assert observation.seeders == 12
    assert observation.leechers == 4
    assert observation.peers == 16


async def test_http_scrape_rejects_oversized_response() -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(200, content=b"x" * 11))
    async with httpx.AsyncClient(transport=transport) as http:
        client = TrackerClient(http, allow_private_addresses=True, max_response_bytes=10)
        with pytest.raises(TrackerError, match="safety limit"):
            await client.scrape("http://tracker.test/announce", HASH)


async def test_http_batch_scrape_groups_hashes_into_one_request() -> None:
    second_hash = "89abcdef0123456789abcdef0123456789abcdef"
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.url.query.count(b"info_hash=") == 2
        files = {
            bytes.fromhex(HASH): {b"complete": 4, b"incomplete": 1},
            bytes.fromhex(second_hash): {b"complete": 9, b"incomplete": 2},
        }
        return httpx.Response(200, content=encode({b"files": files}))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = TrackerClient(http, allow_private_addresses=True)
        verifier = TrackerVerifier(client)
        first = TorrentResult(
            "One", f"magnet:?xt=urn:btih:{HASH}", HASH, trackers=["http://t.test/announce"]
        )
        second = TorrentResult(
            "Two",
            f"magnet:?xt=urn:btih:{second_hash}",
            second_hash,
            trackers=["http://t.test/announce"],
        )
        await verifier.verify_many([first, second])

    assert calls == 1
    assert first.verified_seeders == 4
    assert second.verified_seeders == 9


async def test_udp_scrape_against_local_fake_tracker() -> None:
    class FakeTracker(asyncio.DatagramProtocol):
        transport: asyncio.DatagramTransport

        def connection_made(self, transport: asyncio.BaseTransport) -> None:
            self.transport = transport  # type: ignore[assignment]

        def datagram_received(self, data: bytes, address: tuple[str, int]) -> None:
            action, transaction = struct.unpack("!II", data[8:16])
            if action == 0:
                self.transport.sendto(struct.pack("!IIQ", 0, transaction, 99), address)
            elif action == 2:
                self.transport.sendto(struct.pack("!IIIII", 2, transaction, 6, 20, 3), address)

    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(FakeTracker, local_addr=("127.0.0.1", 0))
    port = transport.get_extra_info("sockname")[1]
    try:
        async with httpx.AsyncClient() as http:
            client = TrackerClient(http, timeout=1, allow_private_addresses=True)
            observation = await client.scrape(f"udp://127.0.0.1:{port}/announce", HASH)
    finally:
        transport.close()

    assert observation.seeders == 6
    assert observation.leechers == 3


def test_http_tracker_without_scrape_convention_is_rejected() -> None:
    with pytest.raises(TrackerError):
        _http_scrape_url("https://tracker.test/tracker", bytes.fromhex(HASH))


def test_udp_protocol_responses_are_validated() -> None:
    assert _parse_udp_connect(struct.pack("!IIQ", 0, 7, 99), 7) == 99
    assert _parse_udp_scrape(struct.pack("!IIIII", 2, 8, 10, 20, 3), 8) == (10, 20, 3)
    with pytest.raises(TrackerError, match="transaction mismatch"):
        _parse_udp_scrape(struct.pack("!IIIII", 2, 9, 10, 20, 3), 8)


async def test_verifier_uses_maximum_instead_of_double_counting() -> None:
    class FakeClient:
        @staticmethod
        def supports(url: str) -> bool:
            return True

        async def scrape(self, tracker: str, info_hash: str) -> TrackerObservation:
            if tracker.endswith("one"):
                return TrackerObservation(tracker, seeders=8, leechers=2)
            return TrackerObservation(tracker, seeders=5, leechers=9)

    result = TorrentResult(
        "Linux",
        f"magnet:?xt=urn:btih:{HASH}",
        HASH,
        trackers=["udp://tracker.test:80/one", "udp://tracker.test:80/two"],
    )
    await TrackerVerifier(FakeClient()).verify(result)  # type: ignore[arg-type]

    assert result.verified_seeders == 8
    assert result.verified_leechers == 9
    assert result.verified_peers == 14
    assert result.trackers_responded == 2
    assert result.verified is True
    assert result.verification_status is VerificationStatus.VERIFIED_SEEDED


async def test_verification_cache_avoids_repeated_tracker_calls(tmp_path: Path) -> None:
    class CountingClient:
        calls = 0

        @staticmethod
        def supports(url: str) -> bool:
            return True

        async def scrape(self, tracker: str, info_hash: str) -> TrackerObservation:
            self.calls += 1
            return TrackerObservation(tracker, seeders=3, leechers=1)

    client = CountingClient()
    verifier = TrackerVerifier(
        client,  # type: ignore[arg-type]
        cache=VerificationCache(tmp_path / "cache.sqlite3", ttl_seconds=300),
    )

    def result() -> TorrentResult:
        return TorrentResult(
            "Linux",
            f"magnet:?xt=urn:btih:{HASH}",
            HASH,
            trackers=["udp://tracker.test:80/announce"],
        )

    first = await verifier.verify(result())
    second = await verifier.verify(result())

    assert client.calls == 1
    assert second.verified_seeders == first.verified_seeders == 3
    assert second.verification_status is VerificationStatus.VERIFIED_SEEDED
