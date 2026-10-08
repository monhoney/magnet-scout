from __future__ import annotations

from collections import Counter
from pathlib import PurePosixPath
from typing import Any

from magnet_scout.models import TorrentResult


def enrich_from_torrent(
    result: TorrentResult,
    torrent: Any,
    *,
    metainfo_url: str | None = None,
    sample_limit: int = 20,
) -> TorrentResult:
    """Copy bounded, non-payload metainfo fields from a parsed torrent."""

    files = list(getattr(torrent, "files", ()) or ())
    paths = [_bounded(str(file), 300) for file in files]
    extensions = Counter(PurePosixPath(path).suffix.casefold() or "[none]" for path in paths)
    result.metainfo_url = metainfo_url
    result.file_count = len(files)
    result.sample_files = paths[:sample_limit]
    result.file_extensions = dict(sorted(extensions.items()))
    result.torrent_comment = _optional_text(getattr(torrent, "comment", None), 2000)
    result.created_by = _optional_text(getattr(torrent, "created_by", None), 300)
    result.torrent_created_at = getattr(torrent, "creation_date", None)
    result.private = getattr(torrent, "private", None)
    result.source = _optional_text(getattr(torrent, "source", None), 300)
    return result


def _optional_text(value: object, limit: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return _bounded(text, limit) if text else None


def _bounded(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 1] + "…"
