import asyncio
import logging
import time

from core.errors import InvalidParamsError
from core.skill_interface import BaseSkill, SkillContext, SkillResult
from core.supabase_client import get_supabase

from SKILLS.supplier_researcher import api_client, cache
from SKILLS.supplier_researcher.schemas import (
    SupplierProduct,
    SupplierResearchInput,
    SupplierResearchOutput,
)

logger = logging.getLogger(__name__)

SKILL_NAME = "supplier-researcher"

VALID_SOURCES = {"aliexpress", "cj", "spocket"}

SOURCE_SEARCH_FN = {
    "aliexpress": api_client.search_aliexpress,
    "cj": api_client.search_cj,
    "spocket": api_client.search_spocket,
}


class SupplierResearcherSkill(BaseSkill[SupplierResearchInput, SupplierResearchOutput]):
    name = SKILL_NAME
    version = "1.0.0"
    description = "Research suppliers across AliExpress, CJDropshipping, and Spocket for dropshipping products"
    consumes_credits = True
    credit_cost = 1

    def validate(self, input: SupplierResearchInput) -> bool:
        if not input.product_name or not input.product_name.strip():
            raise InvalidParamsError(
                message="product_name must not be empty",
                skill=SKILL_NAME,
                code="INVALID_PARAMS",
            )
        invalid_sources = set(input.sources) - VALID_SOURCES
        if invalid_sources:
            raise InvalidParamsError(
                message=f"Invalid sources: {', '.join(sorted(invalid_sources))}. Valid: {', '.join(sorted(VALID_SOURCES))}",
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

        # -- Fetch from all requested sources in parallel ----------------------
        tasks = []
        source_order: list[str] = []
        for source in input.sources:
            if source in SOURCE_SEARCH_FN:
                tasks.append(
                    SOURCE_SEARCH_FN[source](input.product_name, input.limit_per_source)
                )
                source_order.append(source)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # -- Normalize into SupplierProduct list -------------------------------
        products: list[SupplierProduct] = []
        for source_name, result in zip(source_order, results):
            if isinstance(result, Exception):
                logger.warning("Skipping failed source %s: %s", source_name, result)
                continue
            if not isinstance(result, list):
                continue
            for raw in result:
                try:
                    # Calculate margin_at_3x if target_price provided
                    margin = None
                    if input.target_price_usd and input.target_price_usd > 0:
                        total_cost = raw.get("cost_usd", 0) + raw.get("shipping_cost_usd", 0)
                        margin = round(
                            (input.target_price_usd - total_cost) / input.target_price_usd, 4
                        )

                    products.append(
                        SupplierProduct(
                            source=raw.get("source", source_name),
                            product_id=str(raw.get("product_id", "")),
                            title=raw.get("title", ""),
                            cost_usd=float(raw.get("cost_usd", 0)),
                            shipping_cost_usd=float(raw.get("shipping_cost_usd", 0)),
                            shipping_days_min=int(raw.get("shipping_days_min", 0)),
                            shipping_days_max=int(raw.get("shipping_days_max", 0)),
                            moq=int(raw.get("moq", 1)),
                            supplier_rating=raw.get("supplier_rating"),
                            image_urls=raw.get("image_urls", []),
                            product_url=raw.get("product_url", ""),
                            margin_at_3x=margin,
                            in_stock=raw.get("in_stock", True),
                        )
                    )
                except Exception:
                    logger.warning("Failed to parse product from %s: %s", source_name, raw)

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

        output = SupplierResearchOutput(
            total_found=len(products),
            products=products,
            best_price=best_price,
            best_margin=best_margin,
            fastest_shipping=fastest_shipping,
        )

        # -- Persist to Supabase -----------------------------------------------
        try:
            supabase = get_supabase()
            supabase.table("research_results").insert(
                {
                    "user_id": ctx.user_id,
                    "skill": SKILL_NAME,
                    "request_id": ctx.request_id,
                    "input_params": input.model_dump(),
                    "result": output.model_dump(),
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
