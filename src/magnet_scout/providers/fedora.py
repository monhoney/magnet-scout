from __future__ import annotations

import asyncio
import io
import re
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin

import httpx
from torf import Torrent

from magnet_scout.magnets import parse_magnet
from magnet_scout.metainfo import enrich_from_torrent
from magnet_scout.models import TorrentResult
from magnet_scout.network import ResponseTooLarge, request_limited


class _TorrentLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "a":
            return
        href = dict(attrs).get("href")
        if href and unquote(href).casefold().endswith(".torrent"):
            self.links.append(href)


class FedoraProvider:
    """Search Fedora's official, authentication-free BitTorrent catalog."""

    name = "fedora"
    index_url = "https://torrent.fedoraproject.org/torrents/"

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        concurrency: int = 5,
        max_index_bytes: int = 2 * 1024 * 1024,
        max_torrent_bytes: int = 2 * 1024 * 1024,
    ) -> None:
        self.client = client
        self._semaphore = asyncio.Semaphore(concurrency)
        self.max_index_bytes = max_index_bytes
        self.max_torrent_bytes = max_torrent_bytes

    async def search(self, query: str, limit: int) -> list[TorrentResult]:
        terms = [term.casefold() for term in re.findall(r"\w+", query)]
        if not terms:
            return []
        try:
            response = await request_limited(
                self.client, "GET", self.index_url, max_bytes=self.max_index_bytes
            )
        except ResponseTooLarge as exc:
            raise ValueError("Fedora torrent catalog exceeds safety limit") from exc
        response.raise_for_status()
        parser = _TorrentLinkParser()
        parser.feed(response.text)
        matches: list[tuple[str, str]] = []
        for href in dict.fromkeys(parser.links):
            filename = unquote(href.rsplit("/", 1)[-1])
            if all(term in filename.casefold() for term in terms):
                matches.append((filename, urljoin(self.index_url, href)))
        matches.sort(key=lambda item: item[0].casefold())
        values = await asyncio.gather(
            *(self._result(filename, url) for filename, url in matches[:limit]),
            return_exceptions=True,
        )
        return [value for value in values if isinstance(value, TorrentResult)]

    async def _result(self, filename: str, url: str) -> TorrentResult:
        async with self._semaphore:
            try:
                response = await request_limited(
                    self.client, "GET", url, max_bytes=self.max_torrent_bytes
                )
            except ResponseTooLarge as exc:
                raise ValueError("Fedora torrent metainfo exceeds safety limit") from exc
            response.raise_for_status()
            torrent = Torrent.read_stream(io.BytesIO(response.content), validate=True)
        parsed = parse_magnet(str(torrent.magnet()))
        result = TorrentResult(
            title=filename.removesuffix(".torrent"),
            magnet_uri=parsed.canonical_uri,
            info_hash=parsed.info_hash,
            size_bytes=torrent.size,
            providers=[self.name],
            provider_urls=[url],
            trackers=list(parsed.trackers),
        )
        return enrich_from_torrent(result, torrent, metainfo_url=url)
