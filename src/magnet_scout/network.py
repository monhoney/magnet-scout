from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx


class ResponseTooLarge(ValueError):
    """A network response exceeded its configured in-memory safety limit."""


async def request_limited(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    max_bytes: int,
    **kwargs: Any,
) -> httpx.Response:
    """Read at most ``max_bytes`` and return a detached HTTPX response."""

    kwargs.setdefault("follow_redirects", False)
    async with client.stream(method, url, **kwargs) as response:
        content_length = response.headers.get("content-length")
        if content_length is not None:
            try:
                declared_size = int(content_length)
            except ValueError:
                declared_size = None
            if declared_size is not None and declared_size > max_bytes:
                raise ResponseTooLarge(f"response exceeds {max_bytes} byte safety limit")

        content = bytearray()
        async for chunk in response.aiter_bytes():
            if len(content) + len(chunk) > max_bytes:
                raise ResponseTooLarge(f"response exceeds {max_bytes} byte safety limit")
            content.extend(chunk)

        return httpx.Response(
            response.status_code,
            headers=response.headers,
            content=bytes(content),
            request=response.request,
        )


def retry_after_seconds(value: str | None, *, maximum: float = 30.0) -> float:
    """Parse a Retry-After value and clamp it to a bounded delay."""
    if value is None:
        return min(1.0, maximum)
    try:
        delay = float(value)
    except ValueError:
        try:
            when = parsedate_to_datetime(value)
            if when.tzinfo is None:
                when = when.replace(tzinfo=UTC)
            delay = (when - datetime.now(UTC)).total_seconds()
        except (TypeError, ValueError, OverflowError):
            delay = 1.0
    return max(0.0, min(delay, maximum))


async def request_limited_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    max_bytes: int,
    attempts: int = 2,
    max_retry_after: float = 30.0,
    **kwargs: Any,
) -> httpx.Response:
    """Retry bounded requests only when a service explicitly rate-limits them."""
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    response: httpx.Response | None = None
    for attempt in range(attempts):
        response = await request_limited(client, method, url, max_bytes=max_bytes, **kwargs)
        if response.status_code != 429 or attempt == attempts - 1:
            return response
        await asyncio.sleep(
            retry_after_seconds(response.headers.get("retry-after"), maximum=max_retry_after)
        )
    raise AssertionError("retry loop did not return a response")
