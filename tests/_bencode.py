from __future__ import annotations

from collections.abc import Mapping, Sequence


def encode(value: object) -> bytes:
    if isinstance(value, bytes):
        return str(len(value)).encode() + b":" + value
    if isinstance(value, str):
        return encode(value.encode())
    if isinstance(value, int):
        return b"i" + str(value).encode() + b"e"
    if isinstance(value, Mapping):
        pairs: list[tuple[bytes, object]] = []
        for key, item in value.items():
            raw_key = key.encode() if isinstance(key, str) else key
            if not isinstance(raw_key, bytes):
                raise TypeError("bencode dictionary keys must be bytes or strings")
            pairs.append((raw_key, item))
        pairs.sort(key=lambda pair: pair[0])
        return b"d" + b"".join(encode(key) + encode(item) for key, item in pairs) + b"e"
    if isinstance(value, Sequence):
        return b"l" + b"".join(encode(item) for item in value) + b"e"
    raise TypeError(f"unsupported fixture value: {type(value)!r}")
