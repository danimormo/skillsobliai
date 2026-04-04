import asyncio
import json
import logging

import httpx

from core.config import settings
from core.errors import InvalidApiKeyError, UpstreamError

logger = logging.getLogger(__name__)

SKILL_NAME = "supplier-checker"
MAX_RETRIES = 3
BACKOFF_FACTORS = [1, 2, 4]


async def search_aliexpress(
    client: httpx.AsyncClient,
    title: str,
    limit: int = 10,
) -> list[dict]:
    """Search AliExpress products via ScrapeCreators API.

    Returns a list of product dicts sorted by price.
    """
    url = f"{settings.SCRAPECREATORS_BASE_URL}/v1/aliexpress/search"
    headers = {"x-api-key": settings.SCRAPECREATORS_API_KEY}
    params = {"query": title, "limit": limit}

    last_exc: Exception | None = None

    for attempt in range(MAX_RETRIES):
        try:
            response = await client.get(url, headers=headers, params=params, timeout=30.0)

            if response.status_code == 401:
                raise InvalidApiKeyError(
                    message="Invalid ScrapeCreators API key",
                    skill=SKILL_NAME,
                    code="INVALID_API_KEY",
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
            data = response.json()
            products = data.get("data", data.get("products", []))
            return products if isinstance(products, list) else []

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


async def estimate_price_with_ai(title: str) -> dict:
    """Use Anthropic Claude Haiku to estimate supplier cost for a product.

    Returns a dict with keys: supplier_cost_usd, recommended_price_usd,
    market_avg_usd, competition_level.
    """
    import anthropic

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    prompt = (
        f"You are a dropshipping pricing expert. For the product '{title}', "
        "estimate the following in JSON format only (no markdown, no explanation):\n"
        "{\n"
        '  "supplier_cost_usd": <float, estimated AliExpress/CJ cost>,\n'
        '  "recommended_price_usd": <float, recommended retail price>,\n'
        '  "market_avg_usd": <float, average market selling price>,\n'
        '  "competition_level": "<low|medium|high>"\n'
        "}\n"
        "Base your estimates on typical dropshipping margins and AliExpress pricing."
    )

    response = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
    # Parse JSON from response, handling potential markdown wrapping
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.error("Failed to parse AI pricing response: %s", text)
        return {
            "supplier_cost_usd": 0.0,
            "recommended_price_usd": 0.0,
            "market_avg_usd": 0.0,
            "competition_level": "unknown",
        }
