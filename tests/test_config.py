from pathlib import Path

import pytest

from magnet_scout.config import ConfigError, load_torznab_settings


def test_loads_api_key_from_named_environment_variable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        '[[torznab]]\nname = "legal"\nurl = "https://index.test/api"\n'
        'api_key_env = "LEGAL_INDEX_KEY"\n'
    )
    monkeypatch.setenv("LEGAL_INDEX_KEY", "secret")

    settings = load_torznab_settings(path, required=True)

    assert settings[0].name == "legal"
    assert settings[0].api_key() == "secret"


def test_duplicate_names_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        '[[torznab]]\nname = "same"\nurl = "https://one.test/api"\n'
        '[[torznab]]\nname = "same"\nurl = "https://two.test/api"\n'
    )
    with pytest.raises(ConfigError, match="duplicate"):
        load_torznab_settings(path, required=True)
