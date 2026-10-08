import pytest

from magnet_scout.magnets import InvalidMagnet, normalize_info_hash, parse_magnet

HASH = "0123456789abcdef0123456789abcdef01234567"


def test_parse_and_canonicalize_magnet() -> None:
    parsed = parse_magnet(
        f"magnet:?tr=https%3A%2F%2Ftracker.example%2Fa&xt=urn:btih:{HASH.upper()}&dn=Linux"
    )
    assert parsed.info_hash == HASH
    assert parsed.display_name == "Linux"
    assert parsed.trackers == ("https://tracker.example/a",)
    assert parsed.canonical_uri.startswith(f"magnet:?xt=urn:btih:{HASH}")


def test_preserves_web_seed_and_exact_length() -> None:
    parsed = parse_magnet(
        f"magnet:?xt=urn:btih:{HASH}&xl=123&ws=https%3A%2F%2Farchive.test%2Fdownload%2F"
    )
    assert "&xl=123" in parsed.canonical_uri
    assert "&ws=https%3A%2F%2Farchive.test%2Fdownload%2F" in parsed.canonical_uri
    assert parsed.web_seeds == ("https://archive.test/download/",)


def test_base32_hash_normalizes() -> None:
    assert normalize_info_hash("AERUKZ4JVPG66AJDIVTYTK6N54ASGRLH") == HASH


def test_invalid_magnet_rejected() -> None:
    with pytest.raises(InvalidMagnet):
        parse_magnet("https://example.test/file.torrent")


def test_excessive_magnet_input_is_rejected() -> None:
    with pytest.raises(InvalidMagnet, match="safety limit"):
        parse_magnet("magnet:?xt=urn:btih:" + "a" * 40 + "&dn=" + "x" * 20_000)
    fields = "&".join(f"x{i}=1" for i in range(129))
    with pytest.raises(InvalidMagnet, match="too many fields"):
        parse_magnet("magnet:?xt=urn:btih:" + "a" * 40 + "&" + fields)
