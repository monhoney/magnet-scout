from __future__ import annotations

import math
from datetime import UTC, datetime

from magnet_scout.models import Health, TorrentResult


def score_result(result: TorrentResult, now: datetime | None = None) -> TorrentResult:
    now = now or datetime.now(UTC)
    health = 0.0
    peers = result.verified_peers or 0
    if peers:
        health += min(60.0, 15.0 * math.log2(peers + 1))
    if result.tracker_responsive and peers:
        health += 15
    if result.metadata_available:
        health += 10
    health += min(10, max(0, len(result.providers) - 1) * 5)
    if result.reported_seeders:
        health += min(5.0, math.log2(result.reported_seeders + 1))
    freshness: float = 0.0
    if result.last_checked and result.tracker_responsive is True:
        age = max(0.0, (now - result.last_checked.astimezone(UTC)).total_seconds())
        freshness = 5.0 if age <= 900 else max(0.0, 5.0 * (86400 - age) / 85500)
        health += freshness
    result.health_score = round(min(100.0, health), 1)

    confidence: float = 10 + min(45, len(result.providers) * 15)
    confidence += 25 if result.tracker_responsive is True else 0
    confidence += 10 if result.tracker_responsive else 0
    confidence += 10 if result.web_seed_responsive else 0
    confidence += 5 if result.metadata_available else 0
    confidence += freshness * 2
    result.confidence_score = round(min(100.0, confidence), 1)

    has_observation = result.tracker_responsive is True
    if not result.verification_attempted or not has_observation:
        result.health = Health.UNKNOWN
    elif peers == 0 and result.tracker_responsive is not True:
        result.health = Health.UNKNOWN
    elif peers == 0:
        result.health = Health.DEAD
        result.health_score = 0.0
    elif result.health_score >= 80:
        result.health = Health.EXCELLENT
    elif result.health_score >= 60:
        result.health = Health.GOOD
    elif result.health_score >= 40:
        result.health = Health.FAIR
    elif result.health_score > 0:
        result.health = Health.POOR
    else:
        result.health = Health.DEAD
    return result


def rank_key(result: TorrentResult) -> tuple[object, ...]:
    checked = result.last_checked.timestamp() if result.last_checked else -1.0
    return (
        result.verified,
        result.health_score,
        result.verified_peers if result.verified_peers is not None else -1,
        len(result.providers),
        result.web_seed_responsive is True,
        result.confidence_score,
        checked,
        result.reported_seeders if result.reported_seeders is not None else -1,
        result.title.casefold(),
    )
