from __future__ import annotations

import argparse
import os
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def project_version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as stream:
        value = tomllib.load(stream)["project"]["version"]
    if not isinstance(value, str):
        raise ValueError("project.version must be a string")
    return value


def package_version() -> str:
    source = (ROOT / "src" / "magnet_scout" / "__init__.py").read_text()
    match = re.search(r'^__version__ = "([^"]+)"$', source, re.MULTILINE)
    if match is None:
        raise ValueError("magnet_scout.__version__ was not found")
    return match.group(1)


def validate(tag: str | None = None) -> str:
    project = project_version()
    package = package_version()
    if project != package:
        raise ValueError(f"version mismatch: pyproject={project}, package={package}")
    if tag is not None and tag != f"v{project}":
        raise ValueError(f"release tag {tag!r} must equal 'v{project}'")
    return project


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate MagnetScout release metadata")
    parser.add_argument("--tag")
    args = parser.parse_args()
    print(validate(args.tag or os.environ.get("RELEASE_TAG") or None))


if __name__ == "__main__":
    main()
