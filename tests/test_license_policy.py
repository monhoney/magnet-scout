from scripts.check_runtime_licenses import (
    blocked_licenses,
    documented_dependencies,
    is_license_or_notice_file,
    undocumented_dependencies,
)


def test_blocks_strong_and_weak_copyleft_runtime_licenses() -> None:
    packages = {
        "safe": "MIT",
        "gpl": "GPL-3.0-or-later",
        "agpl": "License :: OSI Approved :: GNU Affero General Public License v3",
        "lgpl": "LGPLv2.1",
        "bt": "BitTorrent Open Source License",
    }

    assert set(blocked_licenses(packages)) == {"gpl", "agpl", "lgpl", "bt"}


def test_recognizes_distribution_license_and_notice_files() -> None:
    assert is_license_or_notice_file("package.dist-info/licenses/LICENSE.txt")
    assert is_license_or_notice_file("package.dist-info/COPYING")
    assert is_license_or_notice_file("package.dist-info/NOTICE.md")
    assert not is_license_or_notice_file("package/LICENSE_CHECK.py")
    assert not is_license_or_notice_file("package.dist-info/METADATA")


def test_runtime_dependencies_are_listed_in_third_party_notices() -> None:
    documented = documented_dependencies()
    assert {"click", "certifi", "typing-extensions"} <= documented
    assert undocumented_dependencies({"magnet-scout": "MIT", "click": "BSD-3-Clause"}) == []
    assert undocumented_dependencies({"magnet-scout": "MIT", "new-package": "MIT"}) == [
        "new-package"
    ]
