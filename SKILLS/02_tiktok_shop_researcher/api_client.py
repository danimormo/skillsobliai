"""HTTP client wrapper for ScrapeCreators TikTok Shop Search API."""

from __future__ import annotations

import logging

import httpx

from core.config import settings
from core.http_client import fetch_with_retry

logger = logging.getLogger(__name__)


async def search_tiktok_shop(
    keyword: str,
    country: str,
    client: httpx.AsyncClient | None = None,
) -> list[dict]:
    """Call ScrapeCreators GET /v1/tiktok/shop/search.

    Returns the raw product list (~30 products per call).
    """
    url = f"{settings.SCRAPECREATORS_BASE_URL}/v1/tiktok/shop/search"
    params = {"query": keyword, "region": country}
    headers = {"x-api-key": settings.SCRAPECREATORS_API_KEY}

    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=30)

    try:
        resp = await fetch_with_retry(
            client,
            "GET",
            url,
            params=params,
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()

        # The API may return products under "data", "products", or at top level
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("data", data.get("products", []))
        return []
    finally:
        if own_client:
            await client.aclose()
