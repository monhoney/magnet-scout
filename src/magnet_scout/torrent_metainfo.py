"""Read-only extraction of bounded metadata from v1 and hybrid torrent files."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlencode

from magnet_scout.bencode import BencodeError, BValue, decode_with_spans


class MetainfoError(ValueError):
    """Torrent metainfo is malformed or outside the supported read-only subset."""


@dataclass(frozen=True, slots=True)
class TorrentMetainfo:
    info_hash: str
    name: str | None
    size: int
    files: tuple[str, ...]
    trackers: tuple[str, ...]
    web_seeds: tuple[str, ...]
    comment: str | None
    created_by: str | None
    creation_date: datetime | None
    private: bool | None
    source: str | None

    def magnet_uri(self) -> str:
        query: list[tuple[str, str]] = [("xt", f"urn:btih:{self.info_hash}")]
        if self.name:
            query.append(("dn", self.name))
        query.append(("xl", str(self.size)))
        query.extend(("tr", value) for value in self.trackers)
        query.extend(("ws", value) for value in self.web_seeds)
        return f"magnet:?{urlencode(query)}"


def parse_torrent(data: bytes) -> TorrentMetainfo:
    try:
        decoded = decode_with_spans(data, max_depth=40, max_items=100_000)
        root = _dict(decoded.value, "torrent root")
        info = _dict(root.get(b"info"), "info")
        info_span = decoded.root_value_spans.get(b"info")
        if info_span is None:
            raise MetainfoError("torrent has no info dictionary")
        start, end = info_span
        info_hash = hashlib.sha1(data[start:end], usedforsecurity=False).hexdigest()  # noqa: S324
        name = _text(info.get(b"name.utf-8") or info.get(b"name"), "info name")
        files, size = _files(info, name)
        trackers = _trackers(root)
        web_seeds = _string_list(root.get(b"url-list"), "url-list")
        timestamp = _optional_int(root.get(b"creation date"), "creation date")
        created_at = datetime.fromtimestamp(timestamp, UTC) if timestamp is not None else None
        private_value = _optional_int(info.get(b"private"), "private")
        if private_value not in {None, 0, 1}:
            raise MetainfoError("private must be zero or one")
        return TorrentMetainfo(
            info_hash=info_hash,
            name=name,
            size=size,
            files=files,
            trackers=trackers,
            web_seeds=web_seeds,
            comment=_optional_text(root.get(b"comment.utf-8") or root.get(b"comment")),
            created_by=_optional_text(root.get(b"created by")),
            creation_date=created_at,
            private=None if private_value is None else bool(private_value),
            source=_optional_text(info.get(b"source")),
        )
    except (BencodeError, KeyError, OverflowError, OSError, TypeError, ValueError) as exc:
        if isinstance(exc, MetainfoError):
            raise
        raise MetainfoError("malformed torrent metainfo") from exc


def _files(info: dict[bytes, BValue], name: str | None) -> tuple[tuple[str, ...], int]:
    length = info.get(b"length")
    raw_files = info.get(b"files")
    if length is not None and raw_files is not None:
        raise MetainfoError("info cannot contain both length and files")
    if length is not None:
        size = _nonnegative_int(length, "length")
        return ((name or "[unnamed]",), size)
    if not isinstance(raw_files, list) or not raw_files:
        raise MetainfoError("only v1 or hybrid torrent file layouts are supported")
    paths: list[str] = []
    total = 0
    for index, raw_file in enumerate(raw_files):
        file_info = _dict(raw_file, f"file {index}")
        total += _nonnegative_int(file_info.get(b"length"), f"file {index} length")
        raw_path = file_info.get(b"path.utf-8") or file_info.get(b"path")
        if not isinstance(raw_path, list) or not raw_path:
            raise MetainfoError(f"file {index} has no path")
        parts = [_text(part, f"file {index} path") for part in raw_path]
        if any(not part or part in {".", ".."} or "/" in part or "\\" in part for part in parts):
            raise MetainfoError(f"file {index} has an unsafe path")
        paths.append("/".join(parts))
    return tuple(paths), total


def _trackers(root: dict[bytes, BValue]) -> tuple[str, ...]:
    values: list[str] = []
    announce = _optional_text(root.get(b"announce"))
    if announce:
        values.append(announce)
    tiers = root.get(b"announce-list")
    if tiers is not None:
        if not isinstance(tiers, list):
            raise MetainfoError("announce-list must be a list")
        for tier in tiers:
            if not isinstance(tier, list):
                raise MetainfoError("announce-list tier must be a list")
            values.extend(_text(item, "tracker URL") for item in tier)
    return tuple(dict.fromkeys(value for value in values if value))


def _string_list(value: BValue | None, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    values = value if isinstance(value, list) else [value]
    return tuple(dict.fromkeys(_text(item, field) for item in values))


def _dict(value: BValue | None, field: str) -> dict[bytes, BValue]:
    if not isinstance(value, dict):
        raise MetainfoError(f"{field} must be a dictionary")
    return value


def _text(value: BValue | None, field: str) -> str:
    if not isinstance(value, bytes):
        raise MetainfoError(f"{field} must be bytes")
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MetainfoError(f"{field} must be UTF-8") from exc


def _optional_text(value: BValue | None) -> str | None:
    return None if value is None else _text(value, "text field")


def _nonnegative_int(value: BValue | None, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise MetainfoError(f"{field} must be a nonnegative integer")
    return value


def _optional_int(value: BValue | None, field: str) -> int | None:
    return None if value is None else _nonnegative_int(value, field)
