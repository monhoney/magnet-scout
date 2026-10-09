import pytest

from magnet_scout.bencode import BencodeError, decode


def test_decodes_canonical_values() -> None:
    assert decode(b"d3:barli1e3:fooe3:fooi2ee") == {b"bar": [1, b"foo"], b"foo": 2}


@pytest.mark.parametrize(
    "payload",
    [
        b"i01e",
        b"i-0e",
        b"03:foo",
        b"d1:bi1e1:ai2ee",
        b"d1:ai1e1:ai2ee",
        b"i1ejunk",
        b"l" * 34 + b"e" * 34,
    ],
)
def test_rejects_noncanonical_or_excessive_input(payload: bytes) -> None:
    with pytest.raises(BencodeError):
        decode(payload)


def test_enforces_item_and_string_limits() -> None:
    with pytest.raises(BencodeError, match="item count"):
        decode(b"li1ei2ee", max_items=2)
    with pytest.raises(BencodeError, match="byte string"):
        decode(b"4:spam", max_string_bytes=3)
