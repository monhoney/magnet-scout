from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode, urlsplit

_HEX = re.compile(r"^[0-9a-fA-F]{40}$")
_BASE32 = re.compile(r"^[A-Z2-7]{32}$", re.IGNORECASE)
_MAX_URI_LENGTH = 16 * 1024
_MAX_QUERY_FIELDS = 128
_MAX_DISCOVERY_URLS = 32


class InvalidMagnet(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ParsedMagnet:
    info_hash: str
    display_name: str | None
    trackers: tuple[str, ...]
    web_seeds: tuple[str, ...]
    canonical_uri: str


def normalize_info_hash(value: str) -> str:
    value = value.strip()
    if _HEX.fullmatch(value):
        return value.lower()
    if _BASE32.fullmatch(value):
        try:
            return base64.b32decode(value.upper()).hex()
        except ValueError as exc:
            raise InvalidMagnet("invalid base32 BTIH") from exc
    raise InvalidMagnet("BTIH must be 40 hex or 32 base32 characters")


def parse_magnet(uri: str) -> ParsedMagnet:
    if len(uri) > _MAX_URI_LENGTH:
        raise InvalidMagnet("magnet URI exceeds safety limit")
    parsed = urlsplit(uri)
    if parsed.scheme.lower() != "magnet":
        raise InvalidMagnet("URI scheme must be magnet")
    try:
        params = parse_qs(
            parsed.query,
            keep_blank_values=False,
            max_num_fields=_MAX_QUERY_FIELDS,
        )
    except ValueError as exc:
        raise InvalidMagnet("magnet URI has too many fields") from exc
    hashes = [x[9:] for x in params.get("xt", []) if x.lower().startswith("urn:btih:")]
    if not hashes:
        raise InvalidMagnet("magnet has no urn:btih exact topic")
    info_hash = normalize_info_hash(hashes[0])
    trackers = tuple(dict.fromkeys(params.get("tr", [])))
    web_seeds = tuple(dict.fromkeys(params.get("ws", [])))
    if len(trackers) > _MAX_DISCOVERY_URLS or len(web_seeds) > _MAX_DISCOVERY_URLS:
        raise InvalidMagnet("magnet URI has too many discovery URLs")
    name = params.get("dn", [None])[0]
    query: list[tuple[str, str]] = []
    if name:
        query.append(("dn", name))
    for key in ("xl", "tr", "ws", "xs", "as", "kt", "so"):
        query.extend((key, value) for value in params.get(key, []))
    suffix = f"&{urlencode(query)}" if query else ""
    canonical = f"magnet:?xt=urn:btih:{info_hash}{suffix}"
    return ParsedMagnet(info_hash, name, trackers, web_seeds, canonical)
