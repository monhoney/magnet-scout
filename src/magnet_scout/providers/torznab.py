from __future__ import annotations

from typing import Any
from urllib.parse import urlencode, urlsplit

import httpx
from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

from magnet_scout.magnets import InvalidMagnet, normalize_info_hash, parse_magnet
from magnet_scout.models import TorrentResult
from magnet_scout.network import request_limited


class TorznabError(RuntimeError):
    pass


class TorznabProvider:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        name: str,
        url: str,
        api_key: str | None = None,
        max_response_bytes: int = 2 * 1024 * 1024,
    ) -> None:
        parsed_url = urlsplit(url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
            raise ValueError("Torznab endpoint must be an HTTP(S) URL with a host")
        if parsed_url.username or parsed_url.password:
            raise ValueError("Torznab endpoint must not contain embedded credentials")
        if api_key and parsed_url.scheme != "https":
            raise ValueError("Torznab API keys require an HTTPS endpoint")
        self.client = client
        self.name = f"torznab:{name}"
        self.url = url
        self.api_key = api_key
        self.max_response_bytes = max_response_bytes

    async def search(self, query: str, limit: int) -> list[TorrentResult]:
        params: dict[str, str | int] = {
            "t": "search",
            "q": query,
            "limit": min(limit, 100),
            "o": "xml",
        }
        if self.api_key:
            params["apikey"] = self.api_key
        try:
            response = await request_limited(
                self.client,
                "GET",
                self.url,
                max_bytes=self.max_response_bytes,
                params=params,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise TorznabError(f"{self.name} request failed") from exc
        try:
            root = ET.fromstring(response.content)
        except (ET.ParseError, DefusedXmlException) as exc:
            raise TorznabError(f"{self.name} returned malformed XML") from exc
        results: list[TorrentResult] = []
        for item in root.findall("./channel/item"):
            result = self._parse_item(item)
            if result is not None:
                results.append(result)
        return results[:limit]

    def _parse_item(self, item: Any) -> TorrentResult | None:
        attrs = {
            element.get("name", "").casefold(): element.get("value", "")
            for element in item.findall("./{*}attr")
        }
        magnet_uri = attrs.get("magneturl") or _magnet_link(item)
        raw_hash = attrs.get("infohash", "")
        if magnet_uri:
            try:
                parsed = parse_magnet(magnet_uri)
            except InvalidMagnet:
                return None
        else:
            try:
                info_hash = normalize_info_hash(raw_hash)
            except InvalidMagnet:
                return None
            title = _text(item, "title") or info_hash
            parsed = parse_magnet(
                f"magnet:?{urlencode([('xt', f'urn:btih:{info_hash}'), ('dn', title)])}"
            )
        title = _text(item, "title") or parsed.display_name or parsed.info_hash
        size = _integer(attrs.get("size") or _text(item, "size"))
        if size is None:
            enclosure = item.find("enclosure")
            size = _integer(enclosure.get("length")) if enclosure is not None else None
        seeders = _integer(attrs.get("seeders"))
        peers = _integer(attrs.get("peers"))
        leechers = max(0, peers - seeders) if peers is not None and seeders is not None else None
        provider_url = _non_magnet_link(item)
        return TorrentResult(
            title=title,
            magnet_uri=parsed.canonical_uri,
            info_hash=parsed.info_hash,
            size_bytes=size,
            reported_seeders=seeders,
            reported_leechers=leechers,
            providers=[self.name],
            provider_urls=[provider_url] if provider_url else [],
            trackers=list(parsed.trackers),
        )


def _text(item: Any, name: str) -> str:
    return (item.findtext(name) or "").strip()


def _magnet_link(item: Any) -> str | None:
    candidates = [_text(item, "link"), _text(item, "guid")]
    enclosure = item.find("enclosure")
    if enclosure is not None:
        candidates.append(enclosure.get("url", ""))
    return next((value for value in candidates if value.startswith("magnet:?")), None)


def _non_magnet_link(item: Any) -> str | None:
    return next(
        (
            value
            for value in (_text(item, "comments"), _text(item, "guid"), _text(item, "link"))
            if value.startswith(("http://", "https://"))
        ),
        None,
    )


def _integer(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None
