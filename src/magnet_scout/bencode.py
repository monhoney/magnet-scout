"""Small, strict bencode decoder for bounded tracker and metainfo responses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

BValue: TypeAlias = int | bytes | list["BValue"] | dict[bytes, "BValue"]


class BencodeError(ValueError):
    """Input is not canonical, bounded bencode."""


@dataclass(frozen=True, slots=True)
class Decoded:
    value: BValue
    root_value_spans: dict[bytes, tuple[int, int]]


class _Decoder:
    def __init__(
        self,
        data: bytes,
        *,
        max_depth: int,
        max_items: int,
        max_string_bytes: int,
    ) -> None:
        self.data = data
        self.position = 0
        self.max_depth = max_depth
        self.max_items = max_items
        self.max_string_bytes = max_string_bytes
        self.items = 0
        self.root_value_spans: dict[bytes, tuple[int, int]] = {}

    def decode(self) -> Decoded:
        if not self.data:
            raise BencodeError("empty bencode input")
        value = self._value(0, root=True)
        if self.position != len(self.data):
            raise BencodeError("trailing data after bencode value")
        return Decoded(value, self.root_value_spans)

    def _value(self, depth: int, *, root: bool = False) -> BValue:
        if depth > self.max_depth:
            raise BencodeError("bencode nesting exceeds safety limit")
        self.items += 1
        if self.items > self.max_items:
            raise BencodeError("bencode item count exceeds safety limit")
        if self.position >= len(self.data):
            raise BencodeError("unexpected end of bencode input")
        marker = self.data[self.position]
        if marker == ord("i"):
            return self._integer()
        if marker == ord("l"):
            return self._list(depth)
        if marker == ord("d"):
            return self._dict(depth, root=root)
        if ord("0") <= marker <= ord("9"):
            return self._bytes()
        raise BencodeError("invalid bencode marker")

    def _integer(self) -> int:
        self.position += 1
        end = self.data.find(b"e", self.position)
        if end < 0:
            raise BencodeError("unterminated bencode integer")
        raw = self.data[self.position : end]
        if not raw or raw in {b"-0", b"+0"}:
            raise BencodeError("invalid bencode integer")
        digits = raw[1:] if raw.startswith(b"-") else raw
        if not digits.isdigit() or raw.startswith(b"+"):
            raise BencodeError("invalid bencode integer")
        if len(digits) > 1 and digits.startswith(b"0"):
            raise BencodeError("non-canonical bencode integer")
        if len(digits) > 20:
            raise BencodeError("bencode integer exceeds safety limit")
        self.position = end + 1
        return int(raw)

    def _bytes(self) -> bytes:
        colon = self.data.find(b":", self.position)
        if colon < 0:
            raise BencodeError("unterminated bencode byte length")
        raw_length = self.data[self.position : colon]
        if not raw_length or not raw_length.isdigit():
            raise BencodeError("invalid bencode byte length")
        if len(raw_length) > 1 and raw_length.startswith(b"0"):
            raise BencodeError("non-canonical bencode byte length")
        if len(raw_length) > 12:
            raise BencodeError("bencode byte length exceeds safety limit")
        length = int(raw_length)
        if length > self.max_string_bytes:
            raise BencodeError("bencode byte string exceeds safety limit")
        start = colon + 1
        end = start + length
        if end > len(self.data):
            raise BencodeError("truncated bencode byte string")
        self.position = end
        return self.data[start:end]

    def _list(self, depth: int) -> list[BValue]:
        self.position += 1
        values: list[BValue] = []
        while True:
            if self.position >= len(self.data):
                raise BencodeError("unterminated bencode list")
            if self.data[self.position] == ord("e"):
                self.position += 1
                return values
            values.append(self._value(depth + 1))

    def _dict(self, depth: int, *, root: bool) -> dict[bytes, BValue]:
        self.position += 1
        values: dict[bytes, BValue] = {}
        previous: bytes | None = None
        while True:
            if self.position >= len(self.data):
                raise BencodeError("unterminated bencode dictionary")
            if self.data[self.position] == ord("e"):
                self.position += 1
                return values
            key = self._bytes()
            if previous is not None and key <= previous:
                raise BencodeError("bencode dictionary keys are not strictly sorted")
            previous = key
            start = self.position
            values[key] = self._value(depth + 1)
            if root:
                self.root_value_spans[key] = (start, self.position)


def decode(
    data: bytes,
    *,
    max_depth: int = 32,
    max_items: int = 100_000,
    max_string_bytes: int | None = None,
) -> BValue:
    """Decode one canonical bencode value under explicit resource limits."""

    return decode_with_spans(
        data,
        max_depth=max_depth,
        max_items=max_items,
        max_string_bytes=max_string_bytes,
    ).value


def decode_with_spans(
    data: bytes,
    *,
    max_depth: int = 32,
    max_items: int = 100_000,
    max_string_bytes: int | None = None,
) -> Decoded:
    limit = len(data) if max_string_bytes is None else max_string_bytes
    if max_depth < 1 or max_items < 1 or limit < 0:
        raise ValueError("bencode limits must be positive")
    return _Decoder(
        data,
        max_depth=max_depth,
        max_items=max_items,
        max_string_bytes=limit,
    ).decode()
