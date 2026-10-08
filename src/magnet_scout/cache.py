from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class CachedVerification:
    verified: bool
    verified_peers: int | None
    verified_seeders: int | None
    verified_leechers: int | None
    trackers_checked: int
    trackers_responded: int
    tracker_responsive: bool
    verification_status: str
    checked_at: str


class VerificationCache:
    """Small TTL cache for aggregate tracker observations; stores no peer addresses."""

    def __init__(self, path: Path, ttl_seconds: int = 300) -> None:
        self.path = path
        self.ttl = timedelta(seconds=ttl_seconds)
        self._lock = asyncio.Lock()

    async def get(self, info_hash: str, trackers: list[str]) -> CachedVerification | None:
        async with self._lock:
            return await asyncio.to_thread(self._get, self._key(info_hash, trackers))

    async def put(
        self, info_hash: str, trackers: list[str], observation: CachedVerification
    ) -> None:
        async with self._lock:
            await asyncio.to_thread(self._put, self._key(info_hash, trackers), observation)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=2)
        connection.execute(
            "CREATE TABLE IF NOT EXISTS verification_cache "
            "(cache_key TEXT PRIMARY KEY, checked_at TEXT NOT NULL, payload TEXT NOT NULL)"
        )
        return connection

    def _get(self, key: str) -> CachedVerification | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT checked_at, payload FROM verification_cache WHERE cache_key = ?", (key,)
            ).fetchone()
            if row is None:
                return None
            checked_at = datetime.fromisoformat(row[0]).astimezone(UTC)
            if datetime.now(UTC) - checked_at > self.ttl:
                connection.execute("DELETE FROM verification_cache WHERE cache_key = ?", (key,))
                return None
            data = json.loads(row[1])
            return CachedVerification(**data)

    def _put(self, key: str, observation: CachedVerification) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO verification_cache(cache_key, checked_at, payload) "
                "VALUES (?, ?, ?)",
                (key, observation.checked_at, json.dumps(asdict(observation))),
            )

    @staticmethod
    def _key(info_hash: str, trackers: list[str]) -> str:
        tracker_fingerprint = "\n".join(sorted(set(trackers))).encode()
        return f"{info_hash}:{hashlib.sha256(tracker_fingerprint).hexdigest()}"


def cache_status(root: Path) -> dict[str, Any]:
    verification = root / "verification.sqlite3"
    academic = root / "academic-torrents.xml"
    entries = 0
    if verification.exists():
        try:
            with sqlite3.connect(verification) as connection:
                row = connection.execute("SELECT COUNT(*) FROM verification_cache").fetchone()
                entries = int(row[0]) if row else 0
        except sqlite3.Error:
            entries = -1
    files = [path for path in root.glob("*") if path.is_file()] if root.exists() else []
    return {
        "root": str(root),
        "verification_entries": entries,
        "academic_index_cached": academic.exists(),
        "files": len(files),
        "size_bytes": sum(path.stat().st_size for path in files),
    }


def clear_cache(root: Path) -> list[Path]:
    targets = [
        root / "verification.sqlite3",
        root / "verification.sqlite3-shm",
        root / "verification.sqlite3-wal",
        root / "academic-torrents.xml",
        root / "academic-torrents.meta.json",
        root / "academic-torrents.tmp",
    ]
    removed: list[Path] = []
    for path in targets:
        try:
            path.unlink()
            removed.append(path)
        except FileNotFoundError:
            pass
    return removed
