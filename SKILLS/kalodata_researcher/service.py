"""Kalodata Researcher skill -- discovers high-opportunity TikTok Shop products."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from core.skill_interface import BaseSkill, SkillContext, SkillResult
from core.supabase_client import get_supabase

from .api_client import search_products, get_product_analytics
from .cache import get_cached, set_cached
from .schemas import (
    KalodataProduct,
    KalodataResearchInput,
    KalodataResearchOutput,
)

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class KalodataResearcherSkill(BaseSkill[KalodataResearchInput, KalodataResearchOutput]):
    name = "kalodata-researcher"
    version = "1.0.0"
    description = (
        "Researches TikTok Shop products via Kalodata/ScrapeCreators and "
        "scores them by opportunity (GMV growth, units sold, competition)."
    )
    consumes_credits = True
    credit_cost = 1

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def validate(self, input: KalodataResearchInput) -> bool:
        if not input.keywords:
            return False
        if len(input.keywords) > 3:
            return False
        return True

    # ------------------------------------------------------------------
    # Main execution
    # ------------------------------------------------------------------
    async def run(
        self, input: KalodataResearchInput, ctx: SkillContext
    ) -> SkillResult[KalodataResearchOutput]:
        start = time.perf_counter()
        cache_params = input.model_dump()

        # 1. Check cache
        cached = await get_cached(ctx.user_id, cache_params)
        if cached is not None:
            output = KalodataResearchOutput(**cached)
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return SkillResult(
                success=True,
                data=output,
                cached=True,
                execution_ms=elapsed_ms,
            )

        # 2. Search products for each keyword (concurrently)
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            search_tasks = [
                search_products(
                    keyword=kw,
                    region=input.region,
                    category=input.category,
                    days_range=input.days_range,
                    limit=input.limit,
                    client=client,
                )
                for kw in input.keywords
            ]
            search_results = await asyncio.gather(*search_tasks, return_exceptions=True)

            # Flatten and deduplicate by product_id
            seen_ids: set[str] = set()
            raw_products: list[dict[str, Any]] = []
            for batch in search_results:
                if isinstance(batch, Exception):
                    logger.warning("Skipping failed keyword search: %s", batch)
                    continue
                for p in batch:
                    pid = str(p.get("product_id", p.get("id", "")))
                    if pid and pid not in seen_ids:
                        seen_ids.add(pid)
                        p["product_id"] = pid
                        raw_products.append(p)

            # 3. Enrich each product with analytics (concurrently, capped)
            sem = asyncio.Semaphore(10)

            async def _enrich(product: dict[str, Any]) -> dict[str, Any]:
                async with sem:
                    analytics = await get_product_analytics(
                        product_id=product["product_id"],
                        region=input.region,
                        days_range=input.days_range,
                        client=client,
                    )
                    product.update(analytics)
                    return product

            enriched = await asyncio.gather(
                *[_enrich(p) for p in raw_products],
                return_exceptions=True,
            )

        # 4. Build typed product models and compute opportunity score
        products: list[KalodataProduct] = []
        for item in enriched:
            if isinstance(item, Exception):
                logger.warning("Failed to enrich product: %s", item)
                continue
            try:
                product = _build_product(item)
                products.append(product)
            except Exception:
                logger.warning("Skipping malformed product: %s", item, exc_info=True)

        # 5. Sort by opportunity_score descending, apply limit
        products.sort(key=lambda p: p.opportunity_score, reverse=True)
        products = products[: input.limit]

        output = KalodataResearchOutput(
            total_products=len(products),
            products=products,
            region=input.region,
            days_range=input.days_range,
        )

        # 6. Persist to Supabase
        try:
            supabase = get_supabase()
            supabase.table("research_results").insert(
                {
                    "user_id": ctx.user_id,
                    "skill": self.name,
                    "query_params": input.model_dump(),
                    "result": output.model_dump(),
                    "items_count": output.total_products,
                }
            ).execute()
        except Exception:
            logger.error("Failed to persist research results", exc_info=True)

        # 7. Cache
        await set_cached(ctx.user_id, cache_params, output.model_dump())

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return SkillResult(
            success=True,
            data=output,
            cached=False,
            execution_ms=elapsed_ms,
        )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _build_product(raw: dict[str, Any]) -> KalodataProduct:
    """Normalise raw API data into a KalodataProduct with an opportunity score."""
    gmv_growth = float(raw.get("gmv_growth_pct", raw.get("gmv_growth", 0)))
    units_sold = int(raw.get("units_sold_30d", raw.get("units_sold", 0)))
    shop_count = max(int(raw.get("shop_count", raw.get("shops", 1))), 1)

    opportunity_score = (gmv_growth * units_sold) / shop_count

    price_range = raw.get("price_range", {})
    if not isinstance(price_range, dict):
        price_range = {"min": 0, "max": 0, "currency": "USD"}

    return KalodataProduct(
        product_id=str(raw["product_id"]),
        title=raw.get("title", ""),
        category=raw.get("category", "Unknown"),
        price_range=price_range,
        gmv_30d=float(raw.get("gmv_30d", raw.get("gmv", 0))),
        gmv_growth_pct=gmv_growth,
        units_sold_30d=units_sold,
        shop_count=shop_count,
        top_shop=raw.get("top_shop"),
        opportunity_score=round(opportunity_score, 2),
        thumbnail_url=raw.get("thumbnail_url"),
    )
