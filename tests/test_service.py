import asyncio

from magnet_scout.models import TorrentResult
from magnet_scout.service import SearchService, merge_results

HASH = "0123456789abcdef0123456789abcdef01234567"


def item(provider: str, seeds: int | None = None) -> TorrentResult:
    return TorrentResult(
        title=f"Linux from {provider}",
        magnet_uri=f"magnet:?xt=urn:btih:{HASH}&tr=https%3A%2F%2Ftracker.test%2Fa",
        info_hash=HASH,
        reported_seeders=seeds,
        providers=[provider],
        provider_urls=[f"https://{provider}.test/item"],
    )


def test_deduplicates_and_merges_provenance() -> None:
    merged = merge_results([item("one", 4), item("two", 7)])
    assert len(merged) == 1
    assert merged[0].providers == ["one", "two"]
    assert merged[0].reported_seeders == 7


async def test_provider_failure_is_isolated() -> None:
    class Good:
        name = "good"

        async def search(self, query: str, limit: int) -> list[TorrentResult]:
            return [item("good")]

    class Bad:
        name = "bad"

        async def search(self, query: str, limit: int) -> list[TorrentResult]:
            raise RuntimeError("boom")

    report = await SearchService([Good(), Bad()]).search("linux", top=10)
    assert len(report.results) == 1
    assert report.failures[0].provider == "bad"
    assert report.failures[0].kind == "ERROR"


async def test_min_seeders_excludes_unknown() -> None:
    class Provider:
        name = "test"

        async def search(self, query: str, limit: int) -> list[TorrentResult]:
            return [item("unknown"), item("enough", 10)]

    report = await SearchService([Provider()]).search("linux", top=10, min_seeders=5)
    assert [result.reported_seeders for result in report.results] == [10]


async def test_verified_min_seeders_uses_observed_not_reported_count() -> None:
    candidate = item("test", 999)

    class Provider:
        name = "test"

        async def search(self, query: str, limit: int) -> list[TorrentResult]:
            return [candidate]

    class Verifier:
        async def verify_many(self, results: list[TorrentResult]) -> None:
            for result in results:
                result.verification_attempted = True
                result.tracker_responsive = True
                result.verified_seeders = 2
                result.verified_leechers = 3
                result.verified_peers = 5
                result.verified = True

    report = await SearchService([Provider()], Verifier()).search(
        "linux", top=10, min_seeders=10, verify=True
    )
    assert report.results == []


async def test_search_overfetches_candidates_before_ranking() -> None:
    seen: list[int] = []

    class Provider:
        name = "test"

        async def search(self, query: str, limit: int) -> list[TorrentResult]:
            seen.append(limit)
            return []

    await SearchService([Provider()]).search("linux", top=10)
    assert seen == [30]


async def test_verification_timeout_keeps_partial_results() -> None:
    class Provider:
        name = "test"

        async def search(self, query: str, limit: int) -> list[TorrentResult]:
            return [item("test", 3)]

    class SlowVerifier:
        async def verify_many(self, results: list[TorrentResult]) -> None:
            await asyncio.sleep(1)

    report = await SearchService([Provider()], SlowVerifier()).search(
        "linux", top=10, verify=True, verification_timeout=0.01
    )

    assert len(report.results) == 1
    assert report.failures[0].provider == "verification"
    assert report.failures[0].kind == "TIMEOUT"
