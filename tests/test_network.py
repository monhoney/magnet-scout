import httpx
import pytest

from magnet_scout.network import ResponseTooLarge, request_limited


async def test_limited_request_rejects_declared_oversize() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, headers={"content-length": "100"}, content=b"x")
    )
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(ResponseTooLarge):
            await request_limited(client, "GET", "https://example.test", max_bytes=10)


async def test_limited_request_rejects_streamed_oversize() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"x" * 11))
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(ResponseTooLarge):
            await request_limited(client, "GET", "https://example.test", max_bytes=10)


async def test_limited_request_returns_bounded_content() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"safe"))
    async with httpx.AsyncClient(transport=transport) as client:
        response = await request_limited(client, "GET", "https://example.test", max_bytes=10)
    assert response.content == b"safe"


async def test_limited_request_never_follows_redirects() -> None:
    destinations: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        destinations.append(str(request.url))
        return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, follow_redirects=True) as client:
        response = await request_limited(client, "GET", "https://example.test", max_bytes=10)

    assert response.status_code == 302
    assert destinations == ["https://example.test"]
