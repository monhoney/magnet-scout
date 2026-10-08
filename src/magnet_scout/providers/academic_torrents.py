from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx
from defusedxml import ElementTree as ET

from magnet_scout.magnets import InvalidMagnet, normalize_info_hash, parse_magnet
from magnet_scout.models import TorrentResult
from magnet_scout.network import ResponseTooLarge, request_limited


class AcademicTorrentsProvider:
    name = "academic-torrents"
    index_url = "https://academictorrents.com/database.xml"
    tracker = "http://academictorrents.com/announce.php"

    def __init__(
        self,
        client: httpx.AsyncClient,
        cache_path: Path,
        *,
        cache_ttl: int = 86400,
        max_index_bytes: int = 10 * 1024 * 1024,
    ) -> None:
        self.client = client
        self.cache_path = cache_path
        self.cache_ttl = cache_ttl
        self.max_index_bytes = max_index_bytes
        self._lock = asyncio.Lock()

    async def search(self, query: str, limit: int) -> list[TorrentResult]:
        data = await self._index()
        return await asyncio.to_thread(self._search_xml, data, query, limit)

    async def _index(self) -> bytes:
        async with self._lock:
            cached = await asyncio.to_thread(self._read_fresh_cache)
            if cached is not None:
                return cached
            stale = await asyncio.to_thread(self._read_cache)
            headers = await asyncio.to_thread(self._conditional_headers)
            try:
                response = await request_limited(
                    self.client,
                    "GET",
                    self.index_url,
                    max_bytes=self.max_index_bytes,
                    headers=headers,
                )
                if response.status_code == 304 and stale is not None:
                    await asyncio.to_thread(os.utime, self.cache_path, None)
                    return stale
                response.raise_for_status()
            except (httpx.HTTPError, ResponseTooLarge):
                if stale is not None:
                    return stale
                raise
            data = response.content
            await asyncio.to_thread(self._write_cache, data, response.headers)
            return data

    def _read_fresh_cache(self) -> bytes | None:
        try:
            if time.time() - self.cache_path.stat().st_mtime > self.cache_ttl:
                return None
            return self._read_cache()
        except FileNotFoundError:
            return None

    def _read_cache(self) -> bytes | None:
        try:
            data = self.cache_path.read_bytes()
            return data if len(data) <= self.max_index_bytes else None
        except FileNotFoundError:
            return None

    def _conditional_headers(self) -> dict[str, str]:
        try:
            metadata = json.loads(self.cache_path.with_suffix(".meta.json").read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
        headers: dict[str, str] = {}
        if isinstance(metadata.get("etag"), str):
            headers["If-None-Match"] = metadata["etag"]
        if isinstance(metadata.get("last_modified"), str):
            headers["If-Modified-Since"] = metadata["last_modified"]
        return headers

    def _write_cache(self, data: bytes, headers: httpx.Headers) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.cache_path.with_suffix(".tmp")
        temporary.write_bytes(data)
        temporary.replace(self.cache_path)
        metadata = {
            "etag": headers.get("etag"),
            "last_modified": headers.get("last-modified"),
        }
        meta_path = self.cache_path.with_suffix(".meta.json")
        meta_temporary = meta_path.with_suffix(".tmp")
        meta_temporary.write_text(json.dumps(metadata))
        meta_temporary.replace(meta_path)

    def _search_xml(self, data: bytes, query: str, limit: int) -> list[TorrentResult]:
        terms = [term.casefold() for term in re.findall(r"\w+", query)]
        if not terms:
            return []
        root = ET.fromstring(data)
        matches: list[tuple[int, TorrentResult]] = []
        for item in root.findall("./channel/item"):
            title = _text(item, "title")
            description = _text(item, "description")
            category = _text(item, "category")
            title_folded = title.casefold()
            category_folded = category.casefold()
            description_folded = description.casefold()
            haystack = f"{title_folded}\n{category_folded}\n{description_folded}"
            if not all(term in haystack for term in terms):
                continue
            try:
                info_hash = normalize_info_hash(_text(item, "infohash"))
            except InvalidMagnet:
                continue
            link = _text(item, "link") or f"https://academictorrents.com/details/{info_hash}"
            magnet_params = [
                ("xt", f"urn:btih:{info_hash}"),
                ("dn", title),
                ("tr", self.tracker),
            ]
            magnet = parse_magnet(f"magnet:?{urlencode(magnet_params)}")
            size_text = _text(item, "size")
            size = int(size_text) if size_text.isdigit() else None
            score = sum(
                3 * (term in title_folded)
                + 2 * (term in category_folded)
                + (term in description_folded)
                for term in terms
            )
            matches.append(
                (
                    score,
                    TorrentResult(
                        title=title or info_hash,
                        magnet_uri=magnet.canonical_uri,
                        info_hash=info_hash,
                        size_bytes=size,
                        providers=[self.name],
                        provider_urls=[link],
                        trackers=[self.tracker],
                    ),
                )
            )
        matches.sort(key=lambda pair: (-pair[0], pair[1].title.casefold()))
        return [result for _, result in matches[:limit]]


def _text(item: Any, name: str) -> str:
    return (item.findtext(name) or "").strip()
