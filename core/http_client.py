import asyncio
import logging

import httpx

from core.errors import RateLimitError, UpstreamError

logger = logging.getLogger(__name__)


async def fetch_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    max_retries: int = 3,
    **kwargs,
) -> httpx.Response:
    """Execute an HTTP request with retry on 429 / 5xx."""
    delays = [1, 2, 4]
    last_exc: Exception | None = None

    for attempt in range(max_retries):
        try:
            response = await client.request(method, url, **kwargs)
            if response.status_code == 429:
                if attempt < max_retries - 1:
                    await asyncio.sleep(delays[attempt])
                    continue
                raise RateLimitError("Rate limit exceeded", skill="http", code="RATE_LIMIT")
            if response.status_code >= 500:
                if attempt < max_retries - 1:
                    await asyncio.sleep(delays[attempt])
                    continue
                raise UpstreamError(
                    f"HTTP {response.status_code}", skill="http", code="UPSTREAM"
                )
            return response
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            last_exc = e
            if attempt < max_retries - 1:
                await asyncio.sleep(delays[attempt])
            else:
                raise UpstreamError(str(e), skill="http", code="CONNECTION") from e

    raise UpstreamError(str(last_exc), skill="http", code="CONNECTION")
