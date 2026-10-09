"""Verify that built distributions contain MagnetScout's license and notice files."""

from __future__ import annotations

import argparse
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

REQUIRED = {"LICENSE", "THIRD_PARTY_NOTICES.md"}


def included_notice_names(artifact: Path) -> set[str]:
    if artifact.suffix == ".whl":
        with zipfile.ZipFile(artifact) as archive:
            names = archive.namelist()
    elif artifact.name.endswith(".tar.gz"):
        with tarfile.open(artifact, "r:gz") as archive:
            names = archive.getnames()
    else:
        raise ValueError(f"unsupported distribution format: {artifact}")
    return {PurePosixPath(name).name for name in names} & REQUIRED


def validate_artifact(artifact: Path) -> None:
    missing = REQUIRED - included_notice_names(artifact)
    if missing:
        raise ValueError(f"{artifact.name} is missing: {', '.join(sorted(missing))}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", nargs="+", type=Path)
    args = parser.parse_args()
    for artifact in args.artifacts:
        validate_artifact(artifact)
        print(f"{artifact.name}: required license and notice files found")


if __name__ == "__main__":
    main()
