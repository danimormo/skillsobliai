"""ScrapeCreators HTTP client for the Video Ripper skill."""

from __future__ import annotations

import logging

import httpx

from core.config import settings
from core.errors import UpstreamError
from core.http_client import fetch_with_retry

logger = logging.getLogger(__name__)

SKILL_NAME = "video-ripper"


async def fetch_shop_videos(
    client: httpx.AsyncClient,
    product_id: str,
    limit: int = 20,
) -> list[dict]:
    """Fetch TikTok Shop videos sorted by engagement rate.

    Calls GET /v1/tiktok/shop/videos?product_id={id}&sort_by=engagement_rate.
    Works for ALL regions.

    Returns a list of video dicts.
    """
    url = f"{settings.SCRAPECREATORS_BASE_URL}/v1/tiktok/shop/videos"
    headers = {"x-api-key": settings.SCRAPECREATORS_API_KEY}
    params = {
        "product_id": product_id,
        "sort_by": "engagement_rate",
        "limit": limit,
    }

    response = await fetch_with_retry(
        client, "GET", url, headers=headers, params=params,
    )
    response.raise_for_status()
    body = response.json()
    videos = body.get("data", body.get("videos", []))
    for v in videos:
        v["_source"] = "shop_videos"
    return videos


async def fetch_product_details_videos(
    client: httpx.AsyncClient,
    product_url: str,
    region: str = "US",
) -> list[dict]:
    """Fetch related videos via the product details endpoint.

    Calls GET /v1/tiktok/product?url={url}&get_related_videos=true&region={region}.
    Works ONLY for US products; returns empty list on 500 errors (EU products)
    instead of raising.

    Returns a list of video dicts.
    """
    url = f"{settings.SCRAPECREATORS_BASE_URL}/v1/tiktok/product"
    headers = {"x-api-key": settings.SCRAPECREATORS_API_KEY}
    params = {
        "url": product_url,
        "get_related_videos": "true",
        "region": region,
    }

    try:
        response = await fetch_with_retry(
            client, "GET", url, headers=headers, params=params,
        )
        response.raise_for_status()
    except (httpx.HTTPStatusError, UpstreamError) as exc:
        logger.warning(
            "Product details endpoint failed (region=%s): %s — returning empty list",
            region,
            exc,
        )
        return []

    body = response.json()
    videos = body.get("related_videos", body.get("videos", []))
    for v in videos:
        v["_source"] = "product_details"
    return videos
