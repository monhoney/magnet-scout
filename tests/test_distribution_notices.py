from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path

import pytest

from scripts.check_distribution_notices import validate_artifact


def test_validates_wheel_notices(tmp_path: Path) -> None:
    artifact = tmp_path / "package.whl"
    with zipfile.ZipFile(artifact, "w") as archive:
        archive.writestr("package.dist-info/licenses/LICENSE", "license")
        archive.writestr("package.dist-info/licenses/THIRD_PARTY_NOTICES.md", "notices")

    validate_artifact(artifact)


def test_validates_sdist_notices(tmp_path: Path) -> None:
    artifact = tmp_path / "package.tar.gz"
    license_file = tmp_path / "LICENSE"
    notice_file = tmp_path / "THIRD_PARTY_NOTICES.md"
    license_file.write_text("license")
    notice_file.write_text("notices")
    with tarfile.open(artifact, "w:gz") as archive:
        archive.add(license_file, arcname="package/LICENSE")
        archive.add(notice_file, arcname="package/THIRD_PARTY_NOTICES.md")

    validate_artifact(artifact)


def test_rejects_missing_notices(tmp_path: Path) -> None:
    artifact = tmp_path / "package.whl"
    with zipfile.ZipFile(artifact, "w") as archive:
        archive.writestr("package.dist-info/licenses/LICENSE", "license")

    with pytest.raises(ValueError, match="THIRD_PARTY_NOTICES.md"):
        validate_artifact(artifact)
