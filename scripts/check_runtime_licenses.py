"""Fail CI when the installed runtime dependency closure declares a blocked license."""

from __future__ import annotations

import re
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path, PurePosixPath
from typing import cast

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

BLOCKED = re.compile(
    r"\b(?:AGPL|GPL|LGPL)(?:v?\d)?\b"
    r"|GNU (?:Affero |Lesser )?General Public License"
    r"|BitTorrent Open Source",
    re.IGNORECASE,
)
NOTICE_NAMES = re.compile(
    r"^(?:license|licence|copying|notice)(?:\.(?:txt|md|rst|html?))?$", re.IGNORECASE
)
ROOT = Path(__file__).resolve().parents[1]


def runtime_closure(project: str = "magnet-scout") -> dict[str, str]:
    environment = cast(dict[str, str], default_environment())
    environment["extra"] = ""
    pending = [canonicalize_name(project)]
    seen: dict[str, str] = {}
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        try:
            package = distribution(name)
        except PackageNotFoundError:
            continue
        license_text = package.metadata["License"] if "License" in package.metadata else ""
        classifiers = "; ".join(
            value
            for value in package.metadata.get_all("Classifier", [])
            if value.startswith("License ::")
        )
        seen[name] = "; ".join(value for value in (license_text, classifiers) if value)
        for raw_requirement in package.requires or []:
            requirement = Requirement(raw_requirement)
            if requirement.marker is None or requirement.marker.evaluate(environment):
                pending.append(canonicalize_name(requirement.name))
    return seen


def blocked_licenses(packages: dict[str, str]) -> dict[str, str]:
    return {name: value for name, value in packages.items() if BLOCKED.search(value)}


def is_license_or_notice_file(path: str) -> bool:
    return NOTICE_NAMES.fullmatch(PurePosixPath(path).name) is not None


def missing_license_files(packages: dict[str, str]) -> list[str]:
    missing: list[str] = []
    for name in packages:
        package = distribution(name)
        if not any(is_license_or_notice_file(str(path)) for path in package.files or ()):
            missing.append(name)
    return sorted(missing)


def documented_dependencies() -> set[str]:
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text()
    return {
        canonicalize_name(match.group(1))
        for match in re.finditer(r"^\| `([^`]+)` \|", notices, re.MULTILINE)
    }


def undocumented_dependencies(packages: dict[str, str]) -> list[str]:
    dependencies = set(packages) - {canonicalize_name("magnet-scout")}
    return sorted(dependencies - documented_dependencies())


def main() -> None:
    packages = runtime_closure()
    blocked = blocked_licenses(packages)
    if blocked:
        details = ", ".join(
            f"{name}: {license_text}" for name, license_text in sorted(blocked.items())
        )
        raise SystemExit(f"blocked runtime dependency license detected: {details}")
    missing = missing_license_files(packages)
    if missing:
        raise SystemExit(
            "runtime distributions missing a license or notice file: " + ", ".join(missing)
        )
    undocumented = undocumented_dependencies(packages)
    if undocumented:
        raise SystemExit(
            "runtime distributions missing from THIRD_PARTY_NOTICES.md: " + ", ".join(undocumented)
        )
    print(
        f"checked {len(packages)} runtime distributions; no blocked license metadata found "
        "and all license files are present"
    )


if __name__ == "__main__":
    main()
