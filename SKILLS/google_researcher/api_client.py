"""ScrapeCreators API client for Google Trends and Reddit search data."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from core.config import settings
from core.errors import InvalidApiKeyError, InvalidParamsError, UpstreamError, RateLimitError

logger = logging.getLogger(__name__)

SKILL_NAME = "google-researcher"
_MAX_RETRIES = 3
_BACKOFF_SECONDS = (1, 2, 4)
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def _headers() -> dict[str, str]:
    return {
        "x-api-key": settings.SCRAPECREATORS_API_KEY,
        "Accept": "application/json",
    }


def _base_url() -> str:
    return settings.SCRAPECREATORS_BASE_URL.rstrip("/")


async def _request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Execute an HTTP request with exponential-backoff retry on transient errors."""
    last_exc: Exception | None = None

    for attempt in range(_MAX_RETRIES):
        try:
            response = await client.request(method, url, **kwargs)

            if response.status_code == 401:
                raise InvalidApiKeyError(
                    message="ScrapeCreators API key is invalid or expired",
                    skill=SKILL_NAME,
                    code="INVALID_API_KEY",
                )

            if response.status_code == 422:
                detail = response.json().get("detail", response.text)
                raise InvalidParamsError(
                    message=f"Invalid parameters: {detail}",
                    skill=SKILL_NAME,
                    code="INVALID_PARAMS",
                )

            if response.status_code == 429:
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(_BACKOFF_SECONDS[attempt])
                    continue
                raise RateLimitError(
                    message="ScrapeCreators rate limit exceeded after retries",
                    skill=SKILL_NAME,
                    code="RATE_LIMITED",
                )

            if response.status_code >= 500:
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(_BACKOFF_SECONDS[attempt])
                    continue
                raise UpstreamError(
                    message=f"ScrapeCreators returned {response.status_code}",
                    skill=SKILL_NAME,
                    code="UPSTREAM_ERROR",
                )

            response.raise_for_status()
            return response.json()

        except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES - 1:
                logger.warning(
                    "Transient error on attempt %d for %s: %s", attempt + 1, url, exc
                )
                await asyncio.sleep(_BACKOFF_SECONDS[attempt])
                continue

    raise UpstreamError(
        message=f"ScrapeCreators request failed after {_MAX_RETRIES} retries: {last_exc}",
        skill=SKILL_NAME,
        code="UPSTREAM_ERROR",
    )


async def fetch_google_trends(
    keyword: str,
    region: str = "US",
    days: int = 90,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Fetch Google Trends interest-over-time data for a keyword."""
    params: dict[str, Any] = {
        "keyword": keyword,
        "region": region,
        "days": days,
    }

    url = f"{_base_url()}/v1/google/trends"

    async def _do(c: httpx.AsyncClient) -> dict[str, Any]:
        data = await _request_with_retry(c, "GET", url, params=params, headers=_headers())
        return data

    if client:
        return await _do(client)

    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        return await _do(c)


async def search_reddit(
    keyword: str,
    subreddits: list[str] | None = None,
    limit: int = 25,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """Search Reddit posts for a keyword via ScrapeCreators."""
    params: dict[str, Any] = {
        "keyword": keyword,
        "limit": limit,
    }
    if subreddits:
        params["subreddits"] = ",".join(subreddits)

    url = f"{_base_url()}/v1/reddit/search"

    async def _do(c: httpx.AsyncClient) -> list[dict[str, Any]]:
        data = await _request_with_retry(c, "GET", url, params=params, headers=_headers())
        return data.get("posts", data.get("data", []))

    if client:
        return await _do(client)

    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        return await _do(c)
