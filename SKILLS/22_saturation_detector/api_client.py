import logging

import httpx

from core.errors import UpstreamError

logger = logging.getLogger(__name__)

SKILL_NAME = "saturation-detector"


async def fetch_store_products(client: httpx.AsyncClient, domain: str) -> list[dict]:
    """Fetch product list from a Shopify store's public products.json endpoint.

    Returns a list of product dicts, or an empty list on any failure.
    """
    url = f"https://{domain}/products.json"
    params = {"limit": 250}

    try:
        response = await client.get(url, params=params, timeout=10.0)
        if response.status_code != 200:
            logger.debug("Store %s returned %s", domain, response.status_code)
            return []
        data = response.json()
        return data.get("products", [])
    except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout) as exc:
        logger.debug("Store %s unreachable: %s", domain, exc)
        return []
    except Exception as exc:
        logger.debug("Store %s unexpected error: %s", domain, exc)
        return []
