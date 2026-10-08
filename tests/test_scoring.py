from datetime import UTC, datetime

from magnet_scout.models import Health, TorrentResult
from magnet_scout.scoring import score_result


def test_unverified_result_stays_unknown() -> None:
    result = TorrentResult("x", "magnet:?x", "a" * 40, providers=["a", "b"])
    score_result(result)
    assert result.health is Health.UNKNOWN
    assert result.confidence_score == 40


def test_verified_live_result_scores_health() -> None:
    result = TorrentResult(
        "x",
        "magnet:?x",
        "a" * 40,
        providers=["a", "b"],
        verified=True,
        verification_attempted=True,
        verified_peers=16,
        tracker_responsive=True,
        metadata_available=True,
        last_checked=datetime.now(UTC),
    )
    score_result(result)
    assert result.health is Health.EXCELLENT
    assert result.confidence_score == 90


def test_unresponsive_tracker_remains_unknown_without_confidence_bonus() -> None:
    result = TorrentResult(
        "x",
        "magnet:?x",
        "a" * 40,
        providers=["a"],
        verification_attempted=True,
        tracker_responsive=False,
        last_checked=datetime.now(UTC),
    )
    score_result(result)
    assert result.health is Health.UNKNOWN
    assert result.confidence_score == 25


def test_responsive_tracker_with_zero_peers_is_dead() -> None:
    result = TorrentResult(
        "x",
        "magnet:?x",
        "a" * 40,
        providers=["a"],
        verification_attempted=True,
        verified_peers=0,
        verified_seeders=0,
        tracker_responsive=True,
        last_checked=datetime.now(UTC),
    )
    score_result(result)
    assert result.health is Health.DEAD
    assert result.health_score == 0


def test_responsive_web_seed_does_not_claim_healthy_swarm() -> None:
    result = TorrentResult(
        "x",
        "magnet:?x",
        "a" * 40,
        providers=["a"],
        verification_attempted=True,
        web_seed_responsive=True,
        web_seeds_checked=1,
        web_seeds_responded=1,
        last_checked=datetime.now(UTC),
    )

    score_result(result)

    assert result.health is Health.UNKNOWN
    assert result.health_score == 0
    assert result.confidence_score == 35
