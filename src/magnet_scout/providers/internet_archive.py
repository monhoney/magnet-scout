from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

import httpx

from magnet_scout.magnets import parse_magnet
from magnet_scout.metainfo import enrich_from_torrent
from magnet_scout.models import TorrentResult
from magnet_scout.network import request_limited
from magnet_scout.torrent_metainfo import parse_torrent


class InternetArchiveProvider:
    name = "internet-archive"
    search_url = "https://archive.org/advancedsearch.php"
    metadata_url = "https://archive.org/metadata/{identifier}"
    download_url = "https://archive.org/download/{identifier}/{filename}"

    def __init__(
        self,
        client: httpx.AsyncClient,
        concurrency: int = 5,
        *,
        subjects: tuple[str, ...] = (),
        license_only: bool = False,
        max_search_bytes: int = 2 * 1024 * 1024,
        max_metadata_bytes: int = 8 * 1024 * 1024,
        max_torrent_bytes: int = 2 * 1024 * 1024,
    ) -> None:
        self.client = client
        self._semaphore = asyncio.Semaphore(concurrency)
        self.subjects = subjects
        self.license_only = license_only
        self.max_search_bytes = max_search_bytes
        self.max_metadata_bytes = max_metadata_bytes
        self.max_torrent_bytes = max_torrent_bytes

    async def search(self, query: str, limit: int) -> list[TorrentResult]:
        terms = [term for term in query.split() if term]
        if not terms:
            return []
        term_clauses = [
            f'(title:("{_escape(term)}") OR description:("{_escape(term)}") '
            f'OR subject:("{_escape(term)}"))'
            for term in terms
        ]
        subject_clause = ""
        if self.subjects:
            subjects = " OR ".join(f'subject:("{_escape(subject)}")' for subject in self.subjects)
            subject_clause = f" AND ({subjects})"
        license_clause = " AND licenseurl:*" if self.license_only else ""
        response = await request_limited(
            self.client,
            "GET",
            self.search_url,
            max_bytes=self.max_search_bytes,
            params={
                "q": " AND ".join(term_clauses)
                + ' AND format:"Archive BitTorrent"'
                + subject_clause
                + license_clause,
                "fl[]": ["identifier", "title", "item_size"],
                "rows": min(max(limit * 2, 10), 100),
                "page": 1,
                "output": "json",
            },
        )
        response.raise_for_status()
        docs = response.json().get("response", {}).get("docs", [])
        tasks = [self._result_from_doc(doc) for doc in docs if isinstance(doc, Mapping)]
        values = await asyncio.gather(*tasks, return_exceptions=True)
        results = [value for value in values if isinstance(value, TorrentResult)]
        return results[:limit]

    async def _result_from_doc(self, doc: Mapping[str, Any]) -> TorrentResult | None:
        identifier = str(doc.get("identifier", "")).strip()
        if not identifier:
            return None
        async with self._semaphore:
            meta_response = await request_limited(
                self.client,
                "GET",
                self.metadata_url.format(identifier=identifier),
                max_bytes=self.max_metadata_bytes,
            )
            meta_response.raise_for_status()
            metadata = meta_response.json()
            torrent_file = next(
                (
                    item
                    for item in metadata.get("files", [])
                    if item.get("format") == "Archive BitTorrent"
                    or str(item.get("name", "")).endswith("_archive.torrent")
                ),
                None,
            )
            if not torrent_file or not torrent_file.get("name"):
                return None
            filename = str(torrent_file["name"])
            torrent_response = await request_limited(
                self.client,
                "GET",
                self.download_url.format(
                    identifier=quote(identifier, safe=""), filename=quote(filename, safe="")
                ),
                max_bytes=self.max_torrent_bytes,
            )
            torrent_response.raise_for_status()
            torrent = parse_torrent(torrent_response.content)
            parsed = parse_magnet(torrent.magnet_uri())
            raw_size = doc.get("item_size")
            size = int(raw_size) if raw_size is not None else torrent.size
            title_value = doc.get("title") or metadata.get("metadata", {}).get("title")
            title = str(title_value or identifier)
            item_metadata = metadata.get("metadata", {})
            result = TorrentResult(
                title=title,
                magnet_uri=parsed.canonical_uri,
                info_hash=parsed.info_hash,
                size_bytes=size,
                providers=[self.name],
                provider_urls=[f"https://archive.org/details/{quote(identifier, safe='')}"],
                trackers=list(parsed.trackers),
                web_seeds=list(parsed.web_seeds),
                description=_metadata_text(item_metadata.get("description"), 2000),
                creators=_metadata_values(item_metadata.get("creator"), 20),
                license_url=_metadata_text(item_metadata.get("licenseurl"), 1000),
                rights=_metadata_text(item_metadata.get("rights"), 1000),
            )
            torrent_url = self.download_url.format(
                identifier=quote(identifier, safe=""), filename=quote(filename, safe="")
            )
            return enrich_from_torrent(result, torrent, metainfo_url=torrent_url)


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', r"\"")


def _metadata_values(value: object, limit: int) -> list[str]:
    values = value if isinstance(value, list) else [value]
    return [str(item).strip()[:300] for item in values if item is not None and str(item).strip()][
        :limit
    ]


def _metadata_text(value: object, limit: int) -> str | None:
    values = _metadata_values(value, 20)
    if not values:
        return None
    text = "; ".join(values)
    return text if len(text) <= limit else text[: limit - 1] + "…"
