from __future__ import annotations

import asyncio
import ipaddress
import secrets
import socket
import struct
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote_from_bytes, urlsplit, urlunsplit

import httpx

from magnet_scout.bencode import BencodeError, decode
from magnet_scout.cache import CachedVerification, VerificationCache
from magnet_scout.models import TorrentResult, VerificationStatus
from magnet_scout.network import ResponseTooLarge, request_limited

_UDP_PROTOCOL_ID = 0x41727101980
_SUPPORTED_SCHEMES = {"http", "https", "udp"}


class TrackerError(RuntimeError):
    """A tracker could not provide a valid scrape observation."""


class CompositeVerifier:
    """Apply independent, metadata-only verifiers in a fixed order."""

    def __init__(self, verifiers: Sequence[Any]) -> None:
        self.verifiers = verifiers

    async def verify_many(self, results: list[TorrentResult]) -> None:
        for verifier in self.verifiers:
            await verifier.verify_many(results)


@dataclass(frozen=True, slots=True)
class TrackerObservation:
    tracker: str
    seeders: int
    leechers: int
    completed: int | None = None

    @property
    def peers(self) -> int:
        return self.seeders + self.leechers


class TrackerClient:
    """Read swarm counters through tracker scrape protocols only."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        timeout: float = 5.0,
        allow_private_addresses: bool = False,
        max_response_bytes: int = 1024 * 1024,
    ) -> None:
        self.client = client
        self.timeout = timeout
        self.allow_private_addresses = allow_private_addresses
        self.max_response_bytes = max_response_bytes

    @staticmethod
    def supports(url: str) -> bool:
        parsed = urlsplit(url)
        return parsed.scheme.lower() in _SUPPORTED_SCHEMES and bool(parsed.hostname)

    async def scrape(self, tracker: str, info_hash: str) -> TrackerObservation:
        return (await self.scrape_many(tracker, [info_hash]))[info_hash]

    async def scrape_many(
        self, tracker: str, info_hashes: list[str]
    ) -> dict[str, TrackerObservation]:
        if not info_hashes:
            return {}
        parsed = urlsplit(tracker)
        if parsed.scheme.lower() in {"http", "https"}:
            return await self._scrape_http_many(tracker, info_hashes)
        if parsed.scheme.lower() == "udp":
            results: dict[str, TrackerObservation] = {}
            for start in range(0, len(info_hashes), 74):
                chunk = info_hashes[start : start + 74]
                results.update(await self._scrape_udp_many(tracker, chunk))
            return results
        raise TrackerError(f"unsupported tracker scheme: {parsed.scheme or 'missing'}")

    async def _scrape_http_many(
        self, tracker: str, info_hashes: list[str]
    ) -> dict[str, TrackerObservation]:
        raw_hashes = {info_hash: bytes.fromhex(info_hash) for info_hash in info_hashes}
        url = _http_scrape_url(tracker, list(raw_hashes.values()))
        await self._reject_non_public_host(urlsplit(url).hostname)
        try:
            response = await request_limited(
                self.client,
                "GET",
                url,
                max_bytes=self.max_response_bytes,
                timeout=self.timeout,
                follow_redirects=False,
            )
        except ResponseTooLarge as exc:
            raise TrackerError("tracker response exceeded safety limit") from exc
        if response.is_redirect:
            raise TrackerError("tracker redirects are disabled")
        response.raise_for_status()
        try:
            payload = decode(response.content)
            if not isinstance(payload, dict):
                raise TrackerError("tracker response is not a dictionary")
            failure = payload.get(b"failure reason") or payload.get(b"failure_reason")
            if failure:
                message = (
                    failure.decode(errors="replace") if isinstance(failure, bytes) else failure
                )
                raise TrackerError(f"tracker rejected scrape: {message}")
            files = payload[b"files"]
            if not isinstance(files, dict):
                raise TrackerError("tracker files field is not a dictionary")
            observations: dict[str, TrackerObservation] = {}
            for info_hash, raw_hash in raw_hashes.items():
                stats = files.get(raw_hash)
                if stats is None:
                    continue
                if not isinstance(stats, dict):
                    raise TrackerError("tracker file statistics are not a dictionary")
                observations[info_hash] = TrackerObservation(
                    tracker=tracker,
                    seeders=_nonnegative_int(stats[b"complete"]),
                    leechers=_nonnegative_int(stats[b"incomplete"]),
                    completed=_optional_nonnegative_int(stats.get(b"downloaded")),
                )
            return observations
        except (BencodeError, KeyError, TypeError, ValueError) as exc:
            raise TrackerError("malformed HTTP scrape response") from exc

    async def _scrape_udp_many(
        self, tracker: str, info_hashes: list[str]
    ) -> dict[str, TrackerObservation]:
        parsed = urlsplit(tracker)
        host = parsed.hostname
        port = parsed.port
        if not host or not port:
            raise TrackerError("UDP tracker requires a host and port")
        loop = asyncio.get_running_loop()
        addresses = await loop.getaddrinfo(host, port, type=socket.SOCK_DGRAM)
        allowed = [item for item in addresses if self._address_allowed(str(item[4][0]))]
        if not allowed:
            raise TrackerError("tracker resolved only to non-public addresses")
        family, socktype, protocol, _, address = allowed[0]
        sock = socket.socket(family, socktype, protocol)
        sock.setblocking(False)
        try:
            async with asyncio.timeout(self.timeout):
                connect_tx = secrets.randbits(32)
                await loop.sock_sendto(
                    sock, struct.pack("!QII", _UDP_PROTOCOL_ID, 0, connect_tx), address
                )
                connect_data, _ = await loop.sock_recvfrom(sock, 2048)
                connection_id = _parse_udp_connect(connect_data, connect_tx)

                scrape_tx = secrets.randbits(32)
                raw_hashes = [bytes.fromhex(info_hash) for info_hash in info_hashes]
                await loop.sock_sendto(
                    sock,
                    struct.pack("!QII", connection_id, 2, scrape_tx) + b"".join(raw_hashes),
                    address,
                )
                scrape_data, _ = await loop.sock_recvfrom(sock, 2048)
                values = _parse_udp_scrape_many(scrape_data, scrape_tx, len(info_hashes))
                return {
                    info_hash: TrackerObservation(tracker, seeders, leechers, completed)
                    for info_hash, (seeders, completed, leechers) in zip(
                        info_hashes, values, strict=True
                    )
                }
        except TimeoutError as exc:
            raise TrackerError("UDP tracker timed out") from exc
        finally:
            sock.close()

    async def _reject_non_public_host(self, host: str | None) -> None:
        if not host:
            raise TrackerError("tracker URL has no host")
        if self.allow_private_addresses:
            return
        loop = asyncio.get_running_loop()
        addresses = await loop.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        if not addresses or any(not self._address_allowed(str(item[4][0])) for item in addresses):
            raise TrackerError("tracker resolved to a non-public address")

    def _address_allowed(self, value: str) -> bool:
        return self.allow_private_addresses or ipaddress.ip_address(value).is_global


class TrackerVerifier:
    def __init__(
        self,
        client: TrackerClient,
        *,
        concurrency: int = 10,
        max_trackers: int = 8,
        cache: VerificationCache | None = None,
    ) -> None:
        self.client = client
        self._semaphore = asyncio.Semaphore(concurrency)
        self.max_trackers = max_trackers
        self.cache = cache

    async def verify(self, result: TorrentResult) -> TorrentResult:
        trackers = list(dict.fromkeys(url for url in result.trackers if self.client.supports(url)))[
            : self.max_trackers
        ]
        if not trackers:
            return result
        if self.cache:
            cached = await self.cache.get(result.info_hash, trackers)
            if cached:
                _apply_cached(result, cached)
                return result
        result.verification_attempted = True
        result.trackers_checked = len(trackers)
        result.last_checked = datetime.now(UTC)

        async def observe(url: str) -> TrackerObservation | BaseException:
            async with self._semaphore:
                try:
                    return await self.client.scrape(url, result.info_hash)
                except Exception as exc:
                    return exc

        values = await asyncio.gather(*(observe(url) for url in trackers))
        observations = [value for value in values if isinstance(value, TrackerObservation)]
        result.trackers_responded = len(observations)
        result.tracker_responsive = bool(observations)
        if observations:
            result.verified_seeders = max(item.seeders for item in observations)
            result.verified_leechers = max(item.leechers for item in observations)
            result.verified_peers = max(item.peers for item in observations)
            result.verified = result.verified_peers > 0
            if result.verified_seeders > 0:
                result.verification_status = VerificationStatus.VERIFIED_SEEDED
            elif result.verified_peers > 0:
                result.verification_status = VerificationStatus.VERIFIED_PEERS_ONLY
            else:
                result.verification_status = VerificationStatus.TRACKER_RESPONSIVE
        else:
            result.verification_status = VerificationStatus.UNREACHABLE
        if self.cache:
            await self.cache.put(result.info_hash, trackers, _to_cached(result))
        return result

    async def verify_many(self, results: list[TorrentResult]) -> None:
        pending: list[tuple[TorrentResult, list[str]]] = []
        for result in results:
            trackers = list(
                dict.fromkeys(url for url in result.trackers if self.client.supports(url))
            )[: self.max_trackers]
            if not trackers:
                continue
            cached = await self.cache.get(result.info_hash, trackers) if self.cache else None
            if cached:
                _apply_cached(result, cached)
                continue
            result.verification_attempted = True
            result.trackers_checked = len(trackers)
            result.last_checked = datetime.now(UTC)
            pending.append((result, trackers))

        groups: dict[str, list[TorrentResult]] = {}
        for result, trackers in pending:
            for tracker in trackers:
                groups.setdefault(tracker, []).append(result)

        async def scrape_group(
            tracker: str, grouped_results: list[TorrentResult]
        ) -> dict[str, TrackerObservation]:
            async with self._semaphore:
                try:
                    return await self.client.scrape_many(
                        tracker, [result.info_hash for result in grouped_results]
                    )
                except Exception:
                    return {}

        responses = await asyncio.gather(
            *(scrape_group(tracker, grouped) for tracker, grouped in groups.items())
        )
        observations: dict[str, list[TrackerObservation]] = {}
        for response in responses:
            for info_hash, observation in response.items():
                observations.setdefault(info_hash, []).append(observation)
        for result, trackers in pending:
            _apply_observations(result, observations.get(result.info_hash, []))
            if self.cache:
                await self.cache.put(result.info_hash, trackers, _to_cached(result))


class WebSeedVerifier:
    """Probe web-seed endpoints with HEAD requests and never request payload bytes."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        timeout: float = 5.0,
        concurrency: int = 10,
        max_web_seeds: int = 4,
        allow_private_addresses: bool = False,
    ) -> None:
        self.client = client
        self.timeout = timeout
        self._semaphore = asyncio.Semaphore(concurrency)
        self.max_web_seeds = max_web_seeds
        self._host_guard = TrackerClient(
            client,
            timeout=timeout,
            allow_private_addresses=allow_private_addresses,
        )

    async def verify_many(self, results: list[TorrentResult]) -> None:
        async def probe(url: str) -> bool:
            parsed = urlsplit(url)
            if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
                return False
            async with self._semaphore:
                try:
                    await self._host_guard._reject_non_public_host(parsed.hostname)
                    response = await request_limited(
                        self.client,
                        "HEAD",
                        url,
                        max_bytes=0,
                        timeout=self.timeout,
                        follow_redirects=False,
                    )
                    return response.status_code < 400
                except (httpx.HTTPError, OSError, TrackerError, ResponseTooLarge):
                    return False

        pending: list[tuple[TorrentResult, list[str]]] = []
        probes: list[asyncio.Task[bool]] = []
        for result in results:
            urls = list(dict.fromkeys(result.web_seeds))[: self.max_web_seeds]
            if not urls:
                continue
            result.verification_attempted = True
            result.web_seeds_checked = len(urls)
            result.last_checked = result.last_checked or datetime.now(UTC)
            pending.append((result, urls))
            probes.extend(asyncio.create_task(probe(url)) for url in urls)
        values = await asyncio.gather(*probes)
        offset = 0
        for result, urls in pending:
            responses = values[offset : offset + len(urls)]
            offset += len(urls)
            result.web_seeds_responded = sum(responses)
            result.web_seed_responsive = result.web_seeds_responded > 0


def _to_cached(result: TorrentResult) -> CachedVerification:
    if result.last_checked is None or result.tracker_responsive is None:
        raise ValueError("cannot cache an incomplete verification")
    return CachedVerification(
        verified=result.verified,
        verified_peers=result.verified_peers,
        verified_seeders=result.verified_seeders,
        verified_leechers=result.verified_leechers,
        trackers_checked=result.trackers_checked,
        trackers_responded=result.trackers_responded,
        tracker_responsive=result.tracker_responsive,
        verification_status=result.verification_status.value,
        checked_at=result.last_checked.astimezone(UTC).isoformat(),
    )


def _apply_cached(result: TorrentResult, cached: CachedVerification) -> None:
    result.verified = cached.verified
    result.verification_attempted = True
    result.verified_peers = cached.verified_peers
    result.verified_seeders = cached.verified_seeders
    result.verified_leechers = cached.verified_leechers
    result.trackers_checked = cached.trackers_checked
    result.trackers_responded = cached.trackers_responded
    result.tracker_responsive = cached.tracker_responsive
    result.verification_status = VerificationStatus(cached.verification_status)
    result.last_checked = datetime.fromisoformat(cached.checked_at)


def _apply_observations(result: TorrentResult, observations: list[TrackerObservation]) -> None:
    result.trackers_responded = len(observations)
    result.tracker_responsive = bool(observations)
    if observations:
        result.verified_seeders = max(item.seeders for item in observations)
        result.verified_leechers = max(item.leechers for item in observations)
        result.verified_peers = max(item.peers for item in observations)
        result.verified = result.verified_peers > 0
        if result.verified_seeders > 0:
            result.verification_status = VerificationStatus.VERIFIED_SEEDED
        elif result.verified_peers > 0:
            result.verification_status = VerificationStatus.VERIFIED_PEERS_ONLY
        else:
            result.verification_status = VerificationStatus.TRACKER_RESPONSIVE
    else:
        result.verification_status = VerificationStatus.UNREACHABLE


def _http_scrape_url(tracker: str, info_hashes: bytes | list[bytes]) -> str:
    parsed = urlsplit(tracker)
    segments = parsed.path.rsplit("announce", 1)
    if len(segments) != 2:
        raise TrackerError("HTTP tracker has no conventional scrape endpoint")
    path = "scrape".join(segments)
    hashes = [info_hashes] if isinstance(info_hashes, bytes) else info_hashes
    query = f"{parsed.query}&" if parsed.query else ""
    query += "&".join(f"info_hash={quote_from_bytes(value, safe='')}" for value in hashes)
    return urlunsplit((parsed.scheme, parsed.netloc, path, query, ""))


def _parse_udp_connect(data: bytes, transaction_id: int) -> int:
    if len(data) < 8:
        raise TrackerError("short UDP connect response")
    action, received_tx = struct.unpack("!II", data[:8])
    if received_tx != transaction_id:
        raise TrackerError("UDP connect transaction mismatch")
    if action == 3:
        raise TrackerError(f"UDP tracker error: {data[8:].decode(errors='replace')}")
    if action != 0 or len(data) < 16:
        raise TrackerError("invalid UDP connect response")
    return int(struct.unpack("!Q", data[8:16])[0])


def _parse_udp_scrape(data: bytes, transaction_id: int) -> tuple[int, int, int]:
    return _parse_udp_scrape_many(data, transaction_id, 1)[0]


def _parse_udp_scrape_many(
    data: bytes, transaction_id: int, count: int
) -> list[tuple[int, int, int]]:
    if len(data) < 8:
        raise TrackerError("short UDP scrape response")
    action, received_tx = struct.unpack("!II", data[:8])
    if received_tx != transaction_id:
        raise TrackerError("UDP scrape transaction mismatch")
    if action == 3:
        raise TrackerError(f"UDP tracker error: {data[8:].decode(errors='replace')}")
    expected_size = 8 + 12 * count
    if action != 2 or len(data) < expected_size:
        raise TrackerError("invalid UDP scrape response")
    return [
        struct.unpack("!III", data[offset : offset + 12]) for offset in range(8, expected_size, 12)
    ]


def _nonnegative_int(value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError("expected a non-negative integer")
    return value


def _optional_nonnegative_int(value: Any) -> int | None:
    return None if value is None else _nonnegative_int(value)
