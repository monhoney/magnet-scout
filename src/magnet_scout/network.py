from __future__ import annotations

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
