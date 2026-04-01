import asyncio
import logging

import httpx

from core.config import settings
from core.errors import InvalidApiKeyError, InvalidParamsError, UpstreamError

logger = logging.getLogger(__name__)

SKILL_NAME = "kalodata-ripper"
MAX_RETRIES = 3
BACKOFF_FACTORS = [1, 2, 4]


async def fetch_product_videos(
    product_id: str,
    limit: int = 20,
) -> list[dict]:
    """Fetch TikTok Shop videos for a product from ScrapeCreators.

    Calls GET /v1/tiktok/shop/videos with sort_by=engagement_rate.
    Retries up to 3 times on 429 / 5xx with exponential backoff.

    Returns a list of video dicts containing download_url, views,
    engagement_rate, duration, thumbnail_url, and ad_id.
    """
    url = f"{settings.SCRAPECREATORS_BASE_URL}/v1/tiktok/shop/videos"
    headers = {"x-api-key": settings.SCRAPECREATORS_API_KEY}
    params = {
        "product_id": product_id,
        "sort_by": "engagement_rate",
        "limit": limit,
    }

    last_exc: Exception | None = None

    async with httpx.AsyncClient(timeout=30.0) as client:
        for attempt in range(MAX_RETRIES):
            try:
                response = await client.get(url, headers=headers, params=params)

                if response.status_code == 401:
                    raise InvalidApiKeyError(
                        message="Invalid ScrapeCreators API key",
                        skill=SKILL_NAME,
                        code="INVALID_API_KEY",
                    )

                if response.status_code == 422:
                    raise InvalidParamsError(
                        message=f"Invalid parameters: {response.text}",
                        skill=SKILL_NAME,
                        code="INVALID_PARAMS",
                    )

                if response.status_code == 429 or response.status_code >= 500:
                    wait = BACKOFF_FACTORS[attempt] if attempt < len(BACKOFF_FACTORS) else BACKOFF_FACTORS[-1]
                    logger.warning(
                        "ScrapeCreators %s (attempt %d/%d), retrying in %ds",
                        response.status_code,
                        attempt + 1,
                        MAX_RETRIES,
                        wait,
                    )
                    last_exc = UpstreamError(
                        message=f"Upstream returned {response.status_code}",
                        skill=SKILL_NAME,
                        code="UPSTREAM_ERROR",
                    )
                    await asyncio.sleep(wait)
                    continue

                response.raise_for_status()
                body = response.json()
                return body.get("data", body.get("videos", []))

            except (httpx.ConnectError, httpx.ReadTimeout) as exc:
                wait = BACKOFF_FACTORS[attempt] if attempt < len(BACKOFF_FACTORS) else BACKOFF_FACTORS[-1]
                logger.warning(
                    "ScrapeCreators connection error (attempt %d/%d): %s",
                    attempt + 1,
                    MAX_RETRIES,
                    exc,
                )
                last_exc = exc
                await asyncio.sleep(wait)
                continue

    raise UpstreamError(
        message=f"ScrapeCreators unavailable after {MAX_RETRIES} retries: {last_exc}",
        skill=SKILL_NAME,
        code="UPSTREAM_ERROR",
    )
