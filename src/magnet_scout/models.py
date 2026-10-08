from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class Health(StrEnum):
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    FAIR = "FAIR"
    POOR = "POOR"
    DEAD = "DEAD"
    UNKNOWN = "UNKNOWN"


class VerificationStatus(StrEnum):
    NOT_CHECKED = "NOT_CHECKED"
    VERIFIED_SEEDED = "VERIFIED_SEEDED"
    VERIFIED_PEERS_ONLY = "VERIFIED_PEERS_ONLY"
    TRACKER_RESPONSIVE = "TRACKER_RESPONSIVE"
    UNREACHABLE = "UNREACHABLE"


@dataclass(slots=True)
class TorrentResult:
    title: str
    magnet_uri: str
    info_hash: str
    size_bytes: int | None = None
    reported_seeders: int | None = None
    reported_leechers: int | None = None
    providers: list[str] = field(default_factory=list)
    provider_urls: list[str] = field(default_factory=list)
    metainfo_url: str | None = None
    description: str | None = None
    creators: list[str] = field(default_factory=list)
    license_url: str | None = None
    rights: str | None = None
    file_count: int | None = None
    sample_files: list[str] = field(default_factory=list)
    file_extensions: dict[str, int] = field(default_factory=dict)
    torrent_comment: str | None = None
    created_by: str | None = None
    torrent_created_at: datetime | None = None
    private: bool | None = None
    source: str | None = None
    trackers: list[str] = field(default_factory=list, repr=False)
    web_seeds: list[str] = field(default_factory=list, repr=False)
    verified: bool = False
    verification_attempted: bool = False
    verification_status: VerificationStatus = VerificationStatus.NOT_CHECKED
    verified_peers: int | None = None
    verified_seeders: int | None = None
    verified_leechers: int | None = None
    trackers_checked: int = 0
    trackers_responded: int = 0
    tracker_responsive: bool | None = None
    web_seeds_checked: int = 0
    web_seeds_responded: int = 0
    web_seed_responsive: bool | None = None
    dht_attempted: bool = False
    dht_peers: int | None = None
    metadata_available: bool | None = None
    health_score: float = 0.0
    confidence_score: float = 0.0
    health: Health = Health.UNKNOWN
    last_checked: datetime | None = None

    @property
    def provider(self) -> str | None:
        return self.providers[0] if self.providers else None

    @property
    def provider_url(self) -> str | None:
        return self.provider_urls[0] if self.provider_urls else None

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["health"] = self.health.value
        value["verification_status"] = self.verification_status.value
        if self.last_checked:
            value["last_checked"] = self.last_checked.astimezone(UTC).isoformat()
        if self.torrent_created_at:
            value["torrent_created_at"] = self.torrent_created_at.isoformat()
        return value


@dataclass(slots=True)
class ProviderFailure:
    provider: str
    kind: str
    message: str


@dataclass(slots=True)
class SearchReport:
    query: str
    results: list[TorrentResult]
    failures: list[ProviderFailure] = field(default_factory=list)
