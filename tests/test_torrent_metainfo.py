import hashlib

import pytest

from magnet_scout.torrent_metainfo import MetainfoError, parse_torrent
from tests._bencode import encode


def test_parses_multifile_metadata_and_hashes_original_info_bytes() -> None:
    info = {
        b"files": [
            {b"length": 3, b"path": [b"video.mp4"]},
            {b"length": 2, b"path": [b"docs", b"README.txt"]},
        ],
        b"name": b"example",
        b"piece length": 16384,
        b"pieces": b"x" * 20,
        b"private": 1,
        b"source": b"official",
    }
    payload = encode(
        {
            b"announce": b"https://tracker.test/announce",
            b"announce-list": [[b"https://tracker.test/announce", b"udp://tracker.test:80"]],
            b"comment": b"Public dataset",
            b"created by": b"fixture",
            b"creation date": 1_700_000_000,
            b"info": info,
            b"url-list": [b"https://seed.test/files/"],
        }
    )

    torrent = parse_torrent(payload)

    assert torrent.info_hash == hashlib.sha1(encode(info), usedforsecurity=False).hexdigest()
    assert torrent.size == 5
    assert torrent.files == ("video.mp4", "docs/README.txt")
    assert torrent.trackers == (
        "https://tracker.test/announce",
        "udp://tracker.test:80",
    )
    assert torrent.web_seeds == ("https://seed.test/files/",)
    assert torrent.private is True
    assert "xt=urn%3Abtih%3A" in torrent.magnet_uri()


@pytest.mark.parametrize(
    "info",
    [
        {b"name": b"missing-layout"},
        {b"length": -1, b"name": b"negative"},
        {b"files": [{b"length": 1, b"path": [b"..", b"escape"]}], b"name": b"unsafe"},
    ],
)
def test_rejects_unsupported_or_unsafe_file_layouts(info: object) -> None:
    with pytest.raises(MetainfoError):
        parse_torrent(encode({b"info": info}))
