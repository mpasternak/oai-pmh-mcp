"""Testy transportu HTTP OaiClient na httpx.MockTransport (bez sieci)."""

import httpx
import pytest

from oai_pmh_mcp.client import OaiClient
from oai_pmh_mcp.errors import OaiHttpError

BASE = "https://example.org/oai"


def make_client(handler, sleeps):
    async def fake_sleep(seconds):
        sleeps.append(seconds)

    return OaiClient(transport=httpx.MockTransport(handler), sleep=fake_sleep)


async def test_fetch_sends_verb_and_params():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        return httpx.Response(200, content=b"<OAI-PMH/>")

    client = make_client(handler, [])
    await client.fetch(BASE, "ListRecords", {"metadataPrefix": "oai_dc", "set": None})
    await client.aclose()

    assert "verb=ListRecords" in seen["url"]
    assert "metadataPrefix=oai_dc" in seen["url"]
    assert "set=" not in seen["url"]  # None pominięte


async def test_503_is_retried_then_succeeds():
    calls = {"n": 0}
    sleeps = []

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503, headers={"Retry-After": "2"}, content=b"busy")
        return httpx.Response(200, content=b"<OAI-PMH/>")

    client = make_client(handler, sleeps)
    body = await client.fetch(BASE, "Identify", {})
    await client.aclose()

    assert body == b"<OAI-PMH/>"
    assert calls["n"] == 3
    assert sleeps == [2.0, 2.0]  # odczekał wg Retry-After


async def test_persistent_503_eventually_raises():
    def handler(request):
        return httpx.Response(503, headers={"Retry-After": "1"}, content=b"busy")

    client = make_client(handler, [])
    with pytest.raises(OaiHttpError):
        await client.fetch(BASE, "Identify", {})
    await client.aclose()


async def test_http_404_raises_http_error():
    def handler(request):
        return httpx.Response(404, content=b"not found")

    client = make_client(handler, [])
    with pytest.raises(OaiHttpError):
        await client.fetch(BASE, "Identify", {})
    await client.aclose()


async def test_response_size_limit_enforced_while_streaming():
    # BLOCKER: limit rozmiaru musi być egzekwowany strumieniowo, nie po
    # zbuforowaniu całości. Odpowiedź > 10 MB -> błąd.
    from oai_pmh_mcp.client import MAX_RESPONSE_BYTES

    big = b"x" * (MAX_RESPONSE_BYTES + 1024)

    def handler(request):
        return httpx.Response(200, content=big)

    client = make_client(handler, [])
    with pytest.raises(OaiHttpError):
        await client.fetch(BASE, "ListRecords", {})
    await client.aclose()


async def test_non_http_scheme_rejected():
    # SSRF/LFI: file://, gopher:// itp. nie mogą być pobierane.
    called = {"n": 0}

    def handler(request):
        called["n"] += 1
        return httpx.Response(200, content=b"x")

    client = make_client(handler, [])
    with pytest.raises(OaiHttpError):
        await client.fetch("file:///etc/passwd", "Identify", {})
    await client.aclose()
    assert called["n"] == 0  # żądanie w ogóle nie wyszło
