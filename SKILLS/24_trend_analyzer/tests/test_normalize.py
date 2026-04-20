"""Phase 2a tests — normalizers (text / URL / image)."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from trend_analyzer import normalize  # type: ignore[import-not-found]
from trend_analyzer.cost_tracker import CostTracker  # type: ignore[import-not-found]
from trend_analyzer.normalize.image import normalize_image  # type: ignore[import-not-found]
from trend_analyzer.normalize.text import normalize_text  # type: ignore[import-not-found]
from trend_analyzer.normalize.url import (  # type: ignore[import-not-found]
    extract_visible_text,
    normalize_url,
)

from ._stubs import FakeHTTPResponse, install_fake_anthropic, install_fake_httpx


FIXTURES = Path(__file__).parent / "fixtures"

LLM_PAYLOAD = {
    "primary_keyword": "mini waffle maker",
    "secondary_keywords": ["waffle maker", "breakfast gadget", "non-stick waffle"],
    "category": "kitchen",
    "estimated_retail_price_usd": 24.99,
    "product_attributes": ["compact", "non-stick", "600W", "pink/teal"],
}


# ── text ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_normalize_text_happy(monkeypatch):
    install_fake_anthropic(monkeypatch, payload=LLM_PAYLOAD)
    cost = CostTracker(cap_usd=1.0)

    fp = await normalize_text("mini waffle maker", cost)

    assert fp.primary_keyword == "mini waffle maker"
    assert fp.category == "kitchen"
    assert fp.estimated_retail_price_usd == 24.99
    assert len(fp.secondary_keywords) == 3
    assert fp.source_kind == "text"
    assert cost.total > 0


@pytest.mark.asyncio
async def test_normalize_text_rejects_empty(monkeypatch):
    cost = CostTracker(cap_usd=1.0)
    with pytest.raises(Exception) as exc:
        await normalize_text("   ", cost)
    assert "empty" in exc.value.message.lower()


@pytest.mark.asyncio
async def test_normalize_text_coerces_bad_price(monkeypatch):
    payload = {**LLM_PAYLOAD, "estimated_retail_price_usd": "n/a"}
    install_fake_anthropic(monkeypatch, payload=payload)
    cost = CostTracker(cap_usd=1.0)

    fp = await normalize_text("led strip rgb", cost)
    assert fp.estimated_retail_price_usd is None


# ── url ─────────────────────────────────────────────────────────────────────


def test_extract_visible_text_shopify_pdp():
    html = (FIXTURES / "shopify_pdp.html").read_bytes()
    text = extract_visible_text(html)

    assert "Mini Waffle Maker" in text
    assert "Compact non-stick" in text or "Compact Non-Stick" in text
    # <script> / <style> / <noscript> must be stripped
    assert "dataLayer" not in text
    assert "font-family" not in text
    assert "enable JavaScript" not in text


@pytest.mark.asyncio
async def test_normalize_url_happy(monkeypatch):
    install_fake_anthropic(monkeypatch, payload=LLM_PAYLOAD)
    from trend_analyzer.normalize import url as url_mod  # type: ignore[import-not-found]

    html = (FIXTURES / "shopify_pdp.html").read_bytes()
    install_fake_httpx(
        monkeypatch,
        url_mod,
        FakeHTTPResponse(status_code=200, content=html),
    )
    cost = CostTracker(cap_usd=1.0)

    fp = await normalize_url("https://example.com/products/waffle", cost)
    assert fp.primary_keyword == "mini waffle maker"
    assert fp.source_kind == "url"
    assert fp.raw_input.startswith("https://example.com")


@pytest.mark.asyncio
async def test_normalize_url_http_error(monkeypatch):
    from trend_analyzer.normalize import url as url_mod  # type: ignore[import-not-found]

    install_fake_httpx(
        monkeypatch,
        url_mod,
        FakeHTTPResponse(status_code=404, content=b"not found"),
    )
    cost = CostTracker(cap_usd=1.0)

    with pytest.raises(Exception) as exc:
        await normalize_url("https://example.com/missing", cost)
    assert "404" in exc.value.message


# ── image ───────────────────────────────────────────────────────────────────


JPEG_MAGIC_B64 = base64.b64encode(b"\xff\xd8\xff\xe0" + b"\x00" * 32).decode("ascii")


@pytest.mark.asyncio
async def test_normalize_image_from_b64(monkeypatch):
    install_fake_anthropic(monkeypatch, payload=LLM_PAYLOAD)
    cost = CostTracker(cap_usd=1.0)

    fp = await normalize_image(image_url=None, image_b64=JPEG_MAGIC_B64, cost=cost)
    assert fp.source_kind == "image"
    assert fp.primary_keyword == "mini waffle maker"


@pytest.mark.asyncio
async def test_normalize_image_rejects_both(monkeypatch):
    cost = CostTracker(cap_usd=1.0)
    with pytest.raises(Exception) as exc:
        await normalize_image(image_url="http://x/y.jpg", image_b64="abc", cost=cost)
    assert "one of" in exc.value.message.lower()


@pytest.mark.asyncio
async def test_normalize_image_from_url(monkeypatch):
    install_fake_anthropic(monkeypatch, payload=LLM_PAYLOAD)
    from trend_analyzer.normalize import image as img_mod  # type: ignore[import-not-found]

    install_fake_httpx(
        monkeypatch,
        img_mod,
        FakeHTTPResponse(
            status_code=200,
            content=b"\xff\xd8\xff" + b"\x00" * 100,
            headers={"content-type": "image/jpeg"},
        ),
    )
    cost = CostTracker(cap_usd=1.0)

    fp = await normalize_image(
        image_url="https://cdn.example.com/a.jpg", image_b64=None, cost=cost
    )
    assert fp.primary_keyword == "mini waffle maker"
    assert fp.raw_input.endswith("a.jpg")
