"""Shopify saturation probe — how many stores already sell this product.

Scans a curated list of ~340 active Shopify stores (reusing
``data/shopify_sample_stores.json`` from the existing skill 22) and counts
matches by fuzzy title similarity. Also returns the top-5 competitor
stores + their lowest matching price.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
from pathlib import Path

import httpx
from rapidfuzz import fuzz

from .. import cache
from ..cost_tracker import CostTracker
from ..schemas import CompetitorStore, SaturationSignal

logger = logging.getLogger(__name__)

PROVIDER = "shopify_saturation"

BATCH_SIZE = 20
BATCH_DELAY_S = 0.2
MATCH_THRESHOLD = 78
DEFAULT_SAMPLE_SIZE = 120
REQUEST_TIMEOUT_S = 10.0

_REPO_DATA = Path(__file__).resolve().parents[3] / "data" / "shopify_sample_stores.json"


def _load_store_list() -> list[str]:
    if not _REPO_DATA.exists():
        logger.warning("shopify_saturation: store list missing at %s", _REPO_DATA)
        return []
    with _REPO_DATA.open() as f:
        return json.load(f)


async def fetch(
    primary_keyword: str,
    cost: CostTracker,
    *,
    secondary_keywords: list[str] | None = None,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
    no_cache: bool = False,
) -> SaturationSignal:
    key = _cache_key(primary_keyword, sample_size)

    if not no_cache:
        hit = await cache.get(PROVIDER, key)
        if hit is not None:
            return SaturationSignal.model_validate(hit)

    stores = _load_store_list()
    if not stores:
        return SaturationSignal()

    sample = random.sample(stores, min(sample_size, len(stores)))
    matches: list[CompetitorStore] = []

    async with httpx.AsyncClient(
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=REQUEST_TIMEOUT_S,
    ) as client:
        for start in range(0, len(sample), BATCH_SIZE):
            batch = sample[start : start + BATCH_SIZE]
            tasks = [_fetch_one(client, dom) for dom in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for domain, result in zip(batch, results):
                if isinstance(result, Exception) or not result:
                    continue
                match = _find_match(
                    result, primary_keyword, secondary_keywords or [], domain
                )
                if match is not None:
                    matches.append(match)
            if start + BATCH_SIZE < len(sample):
                await asyncio.sleep(BATCH_DELAY_S)

    matches.sort(key=lambda m: (m.price_usd if m.price_usd is not None else 9999))

    signal = SaturationSignal(
        stores_found=len(matches),
        top_competitors=matches[:5],
    )
    cost.add(
        provider=PROVIDER, operation="scan", usd=0.0,
        units=len(sample), note=primary_keyword,
    )

    if not no_cache:
        await cache.set(PROVIDER, key, signal.model_dump(mode="json"))
    return signal


# ── Internals ──────────────────────────────────────────────────────────────


async def _fetch_one(client: httpx.AsyncClient, domain: str) -> list[dict]:
    url = f"https://{domain}/products.json"
    try:
        resp = await client.get(url, params={"limit": 250})
    except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout):
        return []
    except Exception as exc:
        logger.debug("shopify_saturation: %s raised %s", domain, exc)
        return []

    if resp.status_code != 200:
        return []
    try:
        data = resp.json()
    except ValueError:
        return []
    return data.get("products", []) or []


def _find_match(
    products: list[dict],
    primary: str,
    secondary: list[str],
    domain: str,
) -> CompetitorStore | None:
    needles = [primary] + secondary
    for product in products:
        title = str(product.get("title") or "")
        for needle in needles:
            if fuzz.token_sort_ratio(needle.lower(), title.lower()) >= MATCH_THRESHOLD:
                return CompetitorStore(
                    domain=domain,
                    product_url=_pdp_url(domain, product),
                    price_usd=_first_price(product),
                )
    return None


def _pdp_url(domain: str, product: dict) -> str | None:
    handle = product.get("handle")
    if not handle:
        return None
    return f"https://{domain}/products/{handle}"


def _first_price(product: dict) -> float | None:
    variants = product.get("variants") or []
    for v in variants:
        price = v.get("price")
        if price is None:
            continue
        try:
            return float(price)
        except (TypeError, ValueError):
            continue
    return None


def _cache_key(keyword: str, sample_size: int) -> str:
    payload = f"{keyword.strip().lower()}|{sample_size}"
    return hashlib.sha1(payload.encode()).hexdigest()
