from __future__ import annotations

from typing import Protocol

from magnet_scout.models import TorrentResult


class SearchProvider(Protocol):
    name: str

    async def search(self, query: str, limit: int) -> list[TorrentResult]: ...
