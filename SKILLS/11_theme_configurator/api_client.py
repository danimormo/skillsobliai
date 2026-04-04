import asyncio
import logging
from typing import Any

import httpx

from core.config import settings
from core.errors import RateLimitError, ShopifyError, UpstreamError

logger = logging.getLogger(__name__)

SKILL_NAME = "theme-configurator"
MAX_RETRIES = 3
RETRY_BACKOFF = [1.0, 2.0, 4.0]


class ShopifyThemeClient:
    """Async Shopify Admin REST API client for theme operations."""

    def __init__(self, shop_domain: str, access_token: str) -> None:
        self.shop_domain = shop_domain
        self.access_token = access_token
        api_version = settings.SHOPIFY_API_VERSION
        self.base_url = f"https://{shop_domain}/admin/api/{api_version}"
        self._headers = {
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
    ) -> dict[str, Any]:
        """Execute an HTTP request with retry on 429 / 5xx."""
        url = f"{self.base_url}{path}"
        last_exc: Exception | None = None

        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt in range(MAX_RETRIES):
                try:
                    resp = await client.request(
                        method, url, headers=self._headers, json=json, params=params
                    )
                    if resp.status_code == 429:
                        retry_after = float(
                            resp.headers.get("Retry-After", RETRY_BACKOFF[attempt])
                        )
                        logger.warning(
                            "Shopify 429 on %s, retrying in %.1fs", path, retry_after
                        )
                        await asyncio.sleep(retry_after)
                        continue

                    if resp.status_code >= 500:
                        logger.warning(
                            "Shopify %d on %s, retry %d/%d",
                            resp.status_code,
                            path,
                            attempt + 1,
                            MAX_RETRIES,
                        )
                        await asyncio.sleep(RETRY_BACKOFF[attempt])
                        continue

                    if resp.status_code >= 400:
                        body = resp.text
                        raise ShopifyError(
                            message=f"Shopify {resp.status_code}: {body}",
                            skill=SKILL_NAME,
                            code="SHOPIFY_ERROR",
                        )

                    return resp.json()

                except httpx.HTTPError as exc:
                    last_exc = exc
                    logger.warning(
                        "HTTP error on %s: %s (attempt %d/%d)",
                        path,
                        exc,
                        attempt + 1,
                        MAX_RETRIES,
                    )
                    await asyncio.sleep(RETRY_BACKOFF[attempt])

        if last_exc:
            raise UpstreamError(
                message=f"Shopify request failed after {MAX_RETRIES} retries: {last_exc}",
                skill=SKILL_NAME,
                code="SHOPIFY_RETRY_EXHAUSTED",
            )
        raise RateLimitError(
            message="Shopify rate limit exceeded after retries",
            skill=SKILL_NAME,
            code="SHOPIFY_RATE_LIMIT",
        )

    # -- Public methods ---------------------------------------------------

    async def get_themes(self) -> list[dict]:
        """GET /admin/api/{version}/themes.json"""
        data = await self._request("GET", "/themes.json")
        return data.get("themes", [])

    async def update_theme_settings(
        self, theme_id: str, theme_settings: dict
    ) -> dict:
        """PUT /admin/api/{version}/themes/{theme_id}/assets.json

        Updates the theme settings_data.json asset with the provided settings.
        """
        asset_payload = {
            "asset": {
                "key": "config/settings_data.json",
                "value": __import__("json").dumps(theme_settings),
            }
        }
        data = await self._request(
            "PUT",
            f"/themes/{theme_id}/assets.json",
            json=asset_payload,
        )
        return data.get("asset", data)
