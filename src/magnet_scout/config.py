from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class TorznabSettings:
    name: str
    url: str
    api_key_env: str | None = None

    def api_key(self) -> str | None:
        if not self.api_key_env:
            return None
        value = os.environ.get(self.api_key_env)
        if not value:
            raise ConfigError(f"environment variable {self.api_key_env} is not set")
        return value


def load_torznab_settings(path: Path, *, required: bool = False) -> list[TorznabSettings]:
    try:
        with path.open("rb") as stream:
            data = tomllib.load(stream)
    except FileNotFoundError:
        if required:
            raise ConfigError(f"configuration file does not exist: {path}") from None
        return []
    entries = data.get("torznab", [])
    if not isinstance(entries, list):
        raise ConfigError("config 'torznab' must be an array of tables")
    settings: list[TorznabSettings] = []
    names: set[str] = set()
    for position, raw in enumerate(entries, 1):
        if not isinstance(raw, dict):
            raise ConfigError(f"torznab entry {position} must be a table")
        setting = _parse_torznab(raw, position)
        if setting.name in names:
            raise ConfigError(f"duplicate Torznab name: {setting.name}")
        names.add(setting.name)
        settings.append(setting)
    return settings


def _parse_torznab(raw: dict[str, Any], position: int) -> TorznabSettings:
    name = raw.get("name")
    url = raw.get("url")
    api_key_env = raw.get("api_key_env")
    if not isinstance(name, str) or not name.strip():
        raise ConfigError(f"torznab entry {position} requires a name")
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        raise ConfigError(f"torznab entry {position} requires an HTTP(S) URL")
    if api_key_env is not None and not isinstance(api_key_env, str):
        raise ConfigError(f"torznab entry {position} api_key_env must be a string")
    return TorznabSettings(name.strip(), url, api_key_env)
