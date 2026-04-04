import asyncio
import logging

import httpx

from core.config import settings
from core.errors import InvalidApiKeyError, InvalidParamsError, UpstreamError

logger = logging.getLogger(__name__)

SKILL_NAME = "supplier-researcher"
MAX_RETRIES = 3
BACKOFF_FACTORS = [1, 2, 4]


async def _request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    headers: dict | None = None,
    params: dict | None = None,
    source_label: str = "upstream",
) -> dict:
    """Execute an HTTP request with retry on 429 / 5xx (3 retries, backoff 1s/2s/4s)."""
    last_exc: Exception | None = None

    for attempt in range(MAX_RETRIES):
        try:
            response = await client.request(method, url, headers=headers, params=params)

            if response.status_code == 401:
                raise InvalidApiKeyError(
                    message=f"Invalid API key for {source_label}",
                    skill=SKILL_NAME,
                    code="INVALID_API_KEY",
                )

            if response.status_code == 422:
                raise InvalidParamsError(
                    message=f"Invalid parameters for {source_label}: {response.text}",
                    skill=SKILL_NAME,
                    code="INVALID_PARAMS",
                )

            if response.status_code == 429 or response.status_code >= 500:
                wait = BACKOFF_FACTORS[attempt] if attempt < len(BACKOFF_FACTORS) else BACKOFF_FACTORS[-1]
                logger.warning(
                    "%s returned %s (attempt %d/%d), retrying in %ds",
                    source_label,
                    response.status_code,
                    attempt + 1,
                    MAX_RETRIES,
                    wait,
                )
                last_exc = UpstreamError(
                    message=f"{source_label} returned {response.status_code}",
                    skill=SKILL_NAME,
                    code="UPSTREAM_ERROR",
                )
                await asyncio.sleep(wait)
                continue

            response.raise_for_status()
            return response.json()

        except (httpx.ConnectError, httpx.ReadTimeout) as exc:
            wait = BACKOFF_FACTORS[attempt] if attempt < len(BACKOFF_FACTORS) else BACKOFF_FACTORS[-1]
            logger.warning(
                "%s connection error (attempt %d/%d): %s",
                source_label,
                attempt + 1,
                MAX_RETRIES,
                exc,
            )
            last_exc = exc
            await asyncio.sleep(wait)
            continue

    raise UpstreamError(
        message=f"{source_label} unavailable after {MAX_RETRIES} retries: {last_exc}",
        skill=SKILL_NAME,
        code="UPSTREAM_ERROR",
    )


def _normalize_aliexpress(raw: dict) -> dict:
    """Normalize a single AliExpress product dict to common format."""
    return {
        "source": "aliexpress",
        "product_id": str(raw.get("product_id", raw.get("id", ""))),
        "title": raw.get("title", raw.get("product_title", "")),
        "cost_usd": float(raw.get("target_sale_price", raw.get("price", 0))),
        "shipping_cost_usd": float(raw.get("shipping_cost", 0)),
        "shipping_days_min": int(raw.get("shipping_days_min", raw.get("delivery_days_min", 15))),
        "shipping_days_max": int(raw.get("shipping_days_max", raw.get("delivery_days_max", 45))),
        "moq": int(raw.get("min_order_quantity", raw.get("moq", 1))),
        "supplier_rating": float(raw["seller_rating"]) if raw.get("seller_rating") else None,
        "image_urls": raw.get("image_urls", raw.get("images", [])),
        "product_url": raw.get("product_url", raw.get("url", "")),
        "in_stock": raw.get("in_stock", True),
    }


def _normalize_cj(raw: dict) -> dict:
    """Normalize a single CJDropshipping product dict to common format."""
    return {
        "source": "cj",
        "product_id": str(raw.get("pid", raw.get("id", ""))),
        "title": raw.get("productNameEn", raw.get("name", "")),
        "cost_usd": float(raw.get("sellPrice", raw.get("price", 0))),
        "shipping_cost_usd": float(raw.get("shippingCost", 0)),
        "shipping_days_min": int(raw.get("deliveryDaysMin", raw.get("logisticsDaysMin", 7))),
        "shipping_days_max": int(raw.get("deliveryDaysMax", raw.get("logisticsDaysMax", 20))),
        "moq": int(raw.get("moq", 1)),
        "supplier_rating": float(raw["supplierRating"]) if raw.get("supplierRating") else None,
        "image_urls": raw.get("productImageSet", raw.get("images", [])),
        "product_url": raw.get("productUrl", raw.get("url", "")),
        "in_stock": raw.get("status", "on") == "on",
    }


def _normalize_spocket(raw: dict) -> dict:
    """Normalize a single Spocket product dict to common format."""
    return {
        "source": "spocket",
        "product_id": str(raw.get("id", "")),
        "title": raw.get("title", raw.get("name", "")),
        "cost_usd": float(raw.get("cost", raw.get("price", 0))),
        "shipping_cost_usd": float(raw.get("shipping_cost", 0)),
        "shipping_days_min": int(raw.get("shipping_days_min", raw.get("processing_days", 3))),
        "shipping_days_max": int(raw.get("shipping_days_max", raw.get("delivery_days", 14))),
        "moq": int(raw.get("moq", 1)),
        "supplier_rating": float(raw["rating"]) if raw.get("rating") else None,
        "image_urls": raw.get("images", raw.get("image_urls", [])),
        "product_url": raw.get("url", raw.get("product_url", "")),
        "in_stock": raw.get("in_stock", raw.get("available", True)),
    }


async def search_aliexpress(product_name: str, limit: int = 10) -> list[dict]:
    """Search AliExpress via ScrapeCreators API and return normalized dicts."""
    url = f"{settings.SCRAPECREATORS_BASE_URL}/v1/aliexpress/search"
    headers = {"x-api-key": settings.SCRAPECREATORS_API_KEY}
    params = {"query": product_name, "limit": limit}

    async with httpx.AsyncClient(timeout=30.0) as client:
        data = await _request_with_retry(
            client, "GET", url, headers=headers, params=params, source_label="AliExpress/ScrapeCreators"
        )

    products = data.get("data", data.get("products", data.get("results", [])))
    if not isinstance(products, list):
        products = []
    return [_normalize_aliexpress(p) for p in products[:limit]]


async def search_cj(product_name: str, limit: int = 10) -> list[dict]:
    """Search CJDropshipping API and return normalized dicts."""
    url = "https://developers.cjdropshipping.com/api2.0/v1/product/list"
    headers = {"CJ-Access-Token": settings.CJ_ACCESS_TOKEN}
    params = {"productNameEn": product_name, "pageSize": limit, "pageNum": 1}

    async with httpx.AsyncClient(timeout=30.0) as client:
        data = await _request_with_retry(
            client, "GET", url, headers=headers, params=params, source_label="CJDropshipping"
        )

    products = data.get("data", {})
    if isinstance(products, dict):
        products = products.get("list", products.get("products", []))
    if not isinstance(products, list):
        products = []
    return [_normalize_cj(p) for p in products[:limit]]


async def search_spocket(product_name: str, limit: int = 10) -> list[dict]:
    """Search Spocket API and return normalized dicts."""
    url = "https://api.spocket.co/v2/products"
    headers = {"Authorization": f"Bearer {settings.SPOCKET_API_KEY}"}
    params = {"query": product_name, "limit": limit}

    async with httpx.AsyncClient(timeout=30.0) as client:
        data = await _request_with_retry(
            client, "GET", url, headers=headers, params=params, source_label="Spocket"
        )

    products = data.get("data", data.get("products", data.get("results", [])))
    if not isinstance(products, list):
        products = []
    return [_normalize_spocket(p) for p in products[:limit]]
