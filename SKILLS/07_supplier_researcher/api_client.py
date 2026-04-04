import json
import logging

import httpx
import anthropic
from google.cloud import vision

from core.config import settings
from core.http_client import fetch_with_retry
from core.errors import UpstreamError, GoogleVisionError

logger = logging.getLogger(__name__)


async def search_aliexpress(client: httpx.AsyncClient, query: str, limit: int = 10) -> list[dict]:
    """Search AliExpress via ScrapeCreators API and return raw product dicts."""
    resp = await fetch_with_retry(
        client,
        "GET",
        f"{settings.SCRAPECREATORS_BASE_URL}/v1/aliexpress/search",
        headers={"x-api-key": settings.SCRAPECREATORS_API_KEY},
        params={"query": query, "limit": limit},
    )
    if resp.status_code == 200:
        return resp.json().get("products", resp.json().get("data", []))
    return []


def find_supplier_links_via_vision(image_url: str) -> dict:
    """Use Google Vision Web Detection to find supplier pages from product image."""
    try:
        client = vision.ImageAnnotatorClient()
        image = vision.Image()
        image.source.image_uri = image_url

        response = client.web_detection(image=image)
        web = response.web_detection

        competitor_stores, aliexpress_links, alibaba_links = [], [], []

        for page in (web.pages_with_matching_images or []):
            url = page.url
            if "myshopify.com" in url or "shopify.com" in url:
                competitor_stores.append(url)
            elif "aliexpress.com" in url:
                aliexpress_links.append(url)
            elif "alibaba.com" in url:
                alibaba_links.append(url)

        for match in (web.full_matching_images or []):
            if "aliexpress.com" in match.url:
                aliexpress_links.append(match.url)

        return {
            "competitor_stores": list(set(competitor_stores))[:10],
            "aliexpress_direct": list(set(aliexpress_links))[:5],
            "alibaba_direct": list(set(alibaba_links))[:5],
        }
    except Exception as e:
        raise GoogleVisionError(
            f"Vision API error: {e}",
            skill="supplier-researcher",
            code="VISION_ERROR",
        ) from e


def build_supplier_links_static(title: str) -> dict:
    """Build static search URLs for common supplier marketplaces."""
    from urllib.parse import quote

    q = quote(title)
    return {
        "aliexpress_search": f"https://www.aliexpress.com/wholesale?SearchText={q}",
        "alibaba_search": f"https://www.alibaba.com/trade/search?SearchText={q}",
        "shein_search": f"https://www.shein.com/search?q={q}",
        "temu_search": f"https://www.temu.com/search_result.html?search_key={q}",
    }


async def estimate_supplier_price_with_claude(title: str) -> dict:
    """Use Claude Haiku to estimate supplier cost when no API results are found."""
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = await client.messages.create(
        model=settings.ANTHROPIC_MODEL_FAST,
        max_tokens=200,
        messages=[
            {
                "role": "user",
                "content": (
                    f'Estimate e-commerce supplier cost for: "{title}"\n'
                    "Return ONLY valid JSON: "
                    '{"supplier_cost_usd": float, "recommended_price_usd": float, '
                    '"market_avg_usd": float, "competition_level": "low|medium|high|very_high"}'
                ),
            }
        ],
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())
