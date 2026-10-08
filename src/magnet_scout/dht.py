from __future__ import annotations

import asyncio
import logging
import multiprocessing
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from multiprocessing.connection import Connection
from typing import Any

from magnet_scout.models import TorrentResult, VerificationStatus

log = logging.getLogger(__name__)


class DHTUnavailable(RuntimeError):
    pass


class DHTBatchVerifier:
    """Run BEP 5 peer discovery in a disposable, hard-deadline process."""

    def __init__(self, *, timeout: float = 15.0, peer_limit: int = 50) -> None:
        self.timeout = timeout
        self.peer_limit = peer_limit

    async def verify_many(self, results: list[TorrentResult]) -> None:
        if not results:
            return
        hashes = list(dict.fromkeys(result.info_hash for result in results))
        counts = await asyncio.to_thread(_run_isolated, hashes, self.timeout, self.peer_limit)
        for result in results:
            result.verification_attempted = True
            result.last_checked = result.last_checked or datetime.now(UTC)
            result.dht_attempted = True
            result.dht_peers = counts.get(result.info_hash)
            if result.dht_peers is not None and result.dht_peers > 0:
                result.verified_peers = max(result.verified_peers or 0, result.dht_peers)
                result.verified = True
                if result.verification_status is not VerificationStatus.VERIFIED_SEEDED:
                    result.verification_status = VerificationStatus.VERIFIED_PEERS_ONLY


class CompositeVerifier:
    def __init__(self, verifiers: Sequence[Any]) -> None:
        self.verifiers = verifiers

    async def verify_many(self, results: list[TorrentResult]) -> None:
        for verifier in self.verifiers:
            await verifier.verify_many(results)


def _run_isolated(hashes: list[str], timeout: float, peer_limit: int) -> dict[str, int]:
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    process = context.Process(
        target=_worker,
        args=(child, hashes, max(0.5, timeout - 2.0), peer_limit),
        daemon=True,
    )
    process.start()
    child.close()
    try:
        if not parent.poll(timeout):
            raise TimeoutError("DHT verification exceeded its hard deadline")
        message = parent.recv()
        if not isinstance(message, dict):
            raise DHTUnavailable("DHT worker returned an invalid response")
        if "error" in message:
            raise DHTUnavailable(str(message["error"]))
        counts = message.get("counts")
        if not isinstance(counts, dict):
            raise DHTUnavailable("DHT worker returned no peer counts")
        return {str(key): int(value) for key, value in counts.items()}
    finally:
        parent.close()
        if process.is_alive():
            process.terminate()
        process.join(timeout=1)
        if process.is_alive():
            process.kill()
            process.join(timeout=1)


def _worker(
    connection: Connection, hashes: list[str], active_seconds: float, peer_limit: int
) -> None:
    dht: Any = None
    try:
        try:
            import btpydht  # type: ignore[import-untyped]
        except ImportError:
            connection.send({"error": "DHT extra is not installed; install magnet-scout[dht]"})
            return
        dht = btpydht.DHT()
        dht.start()
        bootstrap = min(5.0, active_seconds / 2)
        time.sleep(bootstrap)
        raw_hashes = {info_hash: bytes.fromhex(info_hash) for info_hash in hashes}
        for raw_hash in raw_hashes.values():
            dht.get_peers(raw_hash, block=False, limit=peer_limit)
        deadline = time.monotonic() + max(0.0, active_seconds - bootstrap)
        while time.monotonic() < deadline:
            time.sleep(0.25)
        counts: dict[str, int] = {}
        for info_hash, raw_hash in raw_hashes.items():
            peers = dht.get_peers(raw_hash, block=False, limit=peer_limit) or []
            counts[info_hash] = len(set(tuple(peer) for peer in peers))
        connection.send({"counts": counts})
    except Exception as exc:
        connection.send({"error": f"{type(exc).__name__}: {exc}"})
    finally:
        connection.close()
        if dht is not None:
            try:
                dht.stop_bg()
            except Exception as exc:
                log.debug("DHT backend shutdown failed: %s", type(exc).__name__)
