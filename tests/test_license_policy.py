from scripts.check_runtime_licenses import blocked_licenses


def test_blocks_strong_and_weak_copyleft_runtime_licenses() -> None:
    packages = {
        "safe": "MIT",
        "gpl": "GPL-3.0-or-later",
        "agpl": "License :: OSI Approved :: GNU Affero General Public License v3",
        "lgpl": "LGPLv2.1",
        "bt": "BitTorrent Open Source License",
    }

    assert set(blocked_licenses(packages)) == {"gpl", "agpl", "lgpl", "bt"}
