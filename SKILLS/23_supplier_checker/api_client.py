import asyncio
import json
import logging

import httpx
import anthropic
from google.cloud import vision

from core.config import settings
from core.errors import GoogleVisionError, InvalidApiKeyError, UpstreamError

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


def find_supplier_via_vision(image_url: str) -> dict:
    """Use Google Vision Web Detection to find AliExpress/Alibaba links from a product image.

    Returns a dict with aliexpress_links and alibaba_links found via reverse image search.
    """
    try:
        client = vision.ImageAnnotatorClient()
        image = vision.Image()
        image.source.image_uri = image_url

        response = client.web_detection(image=image)
        web = response.web_detection

        aliexpress_links, alibaba_links = [], []

        for page in (web.pages_with_matching_images or []):
            url = page.url
            if "aliexpress.com" in url:
                aliexpress_links.append(url)
            elif "alibaba.com" in url:
                alibaba_links.append(url)

        for match in (web.full_matching_images or []):
            if "aliexpress.com" in match.url:
                aliexpress_links.append(match.url)

        return {
            "aliexpress_links": list(set(aliexpress_links))[:5],
            "alibaba_links": list(set(alibaba_links))[:5],
        }
    except Exception as e:
        raise GoogleVisionError(
            f"Vision API error: {e}",
            skill=SKILL_NAME,
            code="VISION_ERROR",
        ) from e


async def estimate_price_with_claude(title: str) -> dict:
    """Use Anthropic Claude Haiku to estimate supplier cost for a product.

    Returns a dict with keys: supplier_cost_usd, recommended_price_usd,
    market_avg_usd, competition_level.
    """
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    prompt = (
        f"You are a dropshipping pricing expert. For the product '{title}', "
        "estimate the following in JSON format only (no markdown, no explanation):\n"
        "{\n"
        '  "supplier_cost_usd": <float, estimated AliExpress cost>,\n'
        '  "recommended_price_usd": <float, recommended retail price>,\n'
        '  "market_avg_usd": <float, average market selling price>,\n'
        '  "competition_level": "<low|medium|high|very_high>"\n'
        "}\n"
        "Base your estimates on typical dropshipping margins and AliExpress pricing."
    )

    response = await client.messages.create(
        model=settings.ANTHROPIC_MODEL_FAST,
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
        logger.error("Failed to parse Claude pricing response: %s", text)
        return {
            "supplier_cost_usd": 0.0,
            "recommended_price_usd": 0.0,
            "market_avg_usd": 0.0,
            "competition_level": "unknown",
        }
