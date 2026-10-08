from datetime import datetime

from magnet_scout.metainfo import enrich_from_torrent
from magnet_scout.models import TorrentResult

HASH = "0123456789abcdef0123456789abcdef01234567"


class FakeFile:
    def __init__(self, path: str) -> None:
        self.path = path

    def __str__(self) -> str:
        return self.path


class FakeTorrent:
    files = [FakeFile("public/video.mp4"), FakeFile("public/README.txt")]
    comment = "Open media collection"
    created_by = "torrent-tool"
    creation_date = datetime(2026, 1, 2, 3, 4, 5)
    private = False
    source = "official"


def test_extracts_bounded_non_payload_metadata() -> None:
    result = TorrentResult("Public video", f"magnet:?xt=urn:btih:{HASH}", HASH)

    enrich_from_torrent(result, FakeTorrent(), metainfo_url="https://example.test/file.torrent")

    assert result.file_count == 2
    assert result.sample_files == ["public/video.mp4", "public/README.txt"]
    assert result.file_extensions == {".mp4": 1, ".txt": 1}
    assert result.torrent_comment == "Open media collection"
    assert result.created_by == "torrent-tool"
    assert result.private is False
    assert result.source == "official"
    assert result.to_dict()["torrent_created_at"] == "2026-01-02T03:04:05"
