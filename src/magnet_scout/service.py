from __future__ import annotations

import asyncio
from typing import Protocol

from magnet_scout.magnets import InvalidMagnet, parse_magnet
from magnet_scout.models import ProviderFailure, SearchReport, TorrentResult
from magnet_scout.providers.base import SearchProvider
from magnet_scout.scoring import rank_key, score_result


class ResultVerifier(Protocol):
    async def verify_many(self, results: list[TorrentResult]) -> None: ...


def merge_results(results: list[TorrentResult]) -> list[TorrentResult]:
    merged: dict[str, TorrentResult] = {}
    for result in results:
        try:
            parsed = parse_magnet(result.magnet_uri)
        except InvalidMagnet:
            continue
        result.info_hash = parsed.info_hash
        result.magnet_uri = parsed.canonical_uri
        result.trackers = list(dict.fromkeys([*result.trackers, *parsed.trackers]))
        result.web_seeds = list(dict.fromkeys([*result.web_seeds, *parsed.web_seeds]))
        current = merged.get(result.info_hash)
        if current is None:
            merged[result.info_hash] = result
            continue
        current.providers = list(dict.fromkeys([*current.providers, *result.providers]))
        current.provider_urls = list(dict.fromkeys([*current.provider_urls, *result.provider_urls]))
        current.creators = list(dict.fromkeys([*current.creators, *result.creators]))
        current.trackers = list(dict.fromkeys([*current.trackers, *result.trackers]))
        current.web_seeds = list(dict.fromkeys([*current.web_seeds, *result.web_seeds]))
        current.size_bytes = current.size_bytes or result.size_bytes
        current.reported_seeders = _maximum(current.reported_seeders, result.reported_seeders)
        current.reported_leechers = _maximum(current.reported_leechers, result.reported_leechers)
        current.metainfo_url = current.metainfo_url or result.metainfo_url
        current.description = _longer(current.description, result.description)
        current.license_url = current.license_url or result.license_url
        current.rights = current.rights or result.rights
        current.file_count = _maximum(current.file_count, result.file_count)
        current.sample_files = list(dict.fromkeys([*current.sample_files, *result.sample_files]))[
            :20
        ]
        current.file_extensions = {
            key: max(current.file_extensions.get(key, 0), result.file_extensions.get(key, 0))
            for key in current.file_extensions.keys() | result.file_extensions.keys()
        }
        current.torrent_comment = current.torrent_comment or result.torrent_comment
        current.created_by = current.created_by or result.created_by
        current.torrent_created_at = current.torrent_created_at or result.torrent_created_at
        current.private = current.private if current.private is not None else result.private
        current.source = current.source or result.source
        if len(result.title) > len(current.title):
            current.title = result.title
    return list(merged.values())


def _maximum(left: int | None, right: int | None) -> int | None:
    values = [value for value in (left, right) if value is not None]
    return max(values) if values else None


def _longer(left: str | None, right: str | None) -> str | None:
    values = [value for value in (left, right) if value]
    return max(values, key=len) if values else None


class SearchService:
    def __init__(
        self, providers: list[SearchProvider], verifier: ResultVerifier | None = None
    ) -> None:
        self.providers = providers
        self.verifier = verifier

    async def search(
        self,
        query: str,
        *,
        top: int,
        min_seeders: int | None = None,
        min_reported_seeders: int | None = None,
        min_verified_seeders: int | None = None,
        verify: bool = False,
        provider_timeout: float | None = None,
        verification_timeout: float | None = None,
    ) -> SearchReport:
        candidate_limit = min(max(top * 3, 10), 100)

        async def search_provider(provider: SearchProvider) -> list[TorrentResult]:
            if provider_timeout is None:
                return await provider.search(query, candidate_limit)
            async with asyncio.timeout(provider_timeout):
                return await provider.search(query, candidate_limit)

        responses = await asyncio.gather(
            *(search_provider(provider) for provider in self.providers),
            return_exceptions=True,
        )
        found: list[TorrentResult] = []
        failures: list[ProviderFailure] = []
        for provider, response in zip(self.providers, responses, strict=True):
            if isinstance(response, BaseException):
                kind = "TIMEOUT" if isinstance(response, TimeoutError) else "ERROR"
                failures.append(ProviderFailure(provider.name, kind, str(response)))
            else:
                found.extend(response)
        results = merge_results(found)
        if verify:
            if self.verifier is None:
                raise RuntimeError("verification requested without a verifier")
            try:
                if verification_timeout is None:
                    await self.verifier.verify_many(results)
                else:
                    async with asyncio.timeout(verification_timeout):
                        await self.verifier.verify_many(results)
            except TimeoutError:
                failures.append(
                    ProviderFailure(
                        "verification",
                        "TIMEOUT",
                        f"verification exceeded {verification_timeout:g}s; "
                        "partial observations kept",
                    )
                )
        if min_seeders is not None:
            results = [item for item in results if _has_min_seeders(item, min_seeders, verify)]
        if min_reported_seeders is not None:
            results = [
                item
                for item in results
                if item.reported_seeders is not None
                and item.reported_seeders >= min_reported_seeders
            ]
        if min_verified_seeders is not None:
            results = [
                item
                for item in results
                if item.verified_seeders is not None
                and item.verified_seeders >= min_verified_seeders
            ]
        for result in results:
            score_result(result)
        results.sort(key=rank_key, reverse=True)
        return SearchReport(query=query, results=results[:top], failures=failures)


def _seed_count(result: TorrentResult, *, verified: bool) -> int | None:
    return result.verified_seeders if verified else result.reported_seeders


def _has_min_seeders(result: TorrentResult, minimum: int, verified: bool) -> bool:
    count = _seed_count(result, verified=verified)
    return count is not None and count >= minimum
