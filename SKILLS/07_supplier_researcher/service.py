import logging
import time

import httpx

from core.errors import InvalidParamsError
from core.skill_interface import BaseSkill, SkillContext, SkillResult
from core.supabase_client import get_supabase

from . import api_client, cache
from .schemas import (
    SupplierProduct,
    SupplierResearchInput,
    SupplierResearchOutput,
)

logger = logging.getLogger(__name__)

SKILL_NAME = "supplier-researcher"


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


class SupplierResearcherSkill(BaseSkill[SupplierResearchInput, SupplierResearchOutput]):
    name = SKILL_NAME
    version = "2.0.0"
    description = "Research suppliers via AliExpress and Google Vision for dropshipping products"
    consumes_credits = True
    credit_cost = 1

    def validate(self, input: SupplierResearchInput) -> bool:
        if not input.product_name or not input.product_name.strip():
            raise InvalidParamsError(
                message="product_name must not be empty",
                skill=SKILL_NAME,
                code="INVALID_PARAMS",
            )
        return True

    async def run(
        self, input: SupplierResearchInput, ctx: SkillContext
    ) -> SkillResult[SupplierResearchOutput]:
        start = time.perf_counter()
        self.validate(input)

        # -- Check cache -------------------------------------------------------
        cache_params = input.model_dump()
        cached_data = await cache.get_cached(ctx.user_id, cache_params)
        if cached_data is not None:
            output = SupplierResearchOutput(**cached_data)
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return SkillResult(
                success=True,
                data=output,
                cached=True,
                execution_ms=elapsed_ms,
            )

        # -- Search AliExpress via ScrapeCreators ------------------------------
        products: list[SupplierProduct] = []
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                raw_products = await api_client.search_aliexpress(
                    client, input.product_name, limit=input.limit_per_source
                )
            for raw in raw_products:
                try:
                    normalized = _normalize_aliexpress(raw)
                    margin = None
                    if input.target_price_usd and input.target_price_usd > 0:
                        total_cost = normalized["cost_usd"] + normalized["shipping_cost_usd"]
                        margin = round(
                            (input.target_price_usd - total_cost) / input.target_price_usd, 4
                        )
                    products.append(
                        SupplierProduct(
                            **normalized,
                            margin_at_3x=margin,
                        )
                    )
                except Exception:
                    logger.warning("Failed to parse AliExpress product: %s", raw)
        except Exception as exc:
            logger.warning("AliExpress search failed: %s", exc)

        # -- Google Vision supplier links (if image URL provided) --------------
        vision_supplier_links: dict = {}
        if input.product_image_url:
            try:
                vision_supplier_links = api_client.find_supplier_links_via_vision(
                    input.product_image_url
                )
            except Exception as exc:
                logger.warning("Google Vision lookup failed: %s", exc)

        # -- Static supplier links (always) ------------------------------------
        supplier_links_static = api_client.build_supplier_links_static(input.product_name)

        # -- Compute summary picks ---------------------------------------------
        best_price: SupplierProduct | None = None
        best_margin: SupplierProduct | None = None
        fastest_shipping: SupplierProduct | None = None

        if products:
            best_price = min(products, key=lambda p: p.cost_usd + p.shipping_cost_usd)
            fastest_shipping = min(products, key=lambda p: p.shipping_days_min)

            with_margin = [p for p in products if p.margin_at_3x is not None]
            if with_margin:
                best_margin = max(with_margin, key=lambda p: p.margin_at_3x)  # type: ignore[arg-type]

        # -- Estimate price via Claude Haiku if no API results -----------------
        price_estimate: dict | None = None
        if not products:
            try:
                price_estimate = await api_client.estimate_supplier_price_with_claude(
                    input.product_name
                )
            except Exception:
                logger.exception("Failed to get price estimate from Claude for %s", input.product_name)

        output = SupplierResearchOutput(
            total_found=len(products),
            products=products,
            best_price=best_price,
            best_margin=best_margin,
            fastest_shipping=fastest_shipping,
            supplier_links_static=supplier_links_static,
            vision_supplier_links=vision_supplier_links,
            price_estimate=price_estimate,
        )

        # -- Persist to Supabase -----------------------------------------------
        try:
            supabase = get_supabase()
            supabase.table("research_results").insert(
                {
                    "user_id": ctx.user_id,
                    "skill": SKILL_NAME,
                    "query_params": input.model_dump(),
                    "result": output.model_dump(),
                    "items_count": output.total_found,
                }
            ).execute()
        except Exception:
            logger.exception("Failed to persist research results to Supabase")

        # -- Cache result ------------------------------------------------------
        await cache.set_cached(ctx.user_id, cache_params, output.model_dump())

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return SkillResult(
            success=True,
            data=output,
            cached=False,
            execution_ms=elapsed_ms,
        )
