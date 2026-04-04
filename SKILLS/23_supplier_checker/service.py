import logging
import time

import httpx

from core.errors import InvalidParamsError, UpstreamError
from core.skill_interface import BaseSkill, SkillContext, SkillResult

from SKILLS.supplier_checker import api_client, cache
from SKILLS.supplier_checker.schemas import (
    SupplierCheckerInput,
    SupplierCheckerOutput,
)

logger = logging.getLogger(__name__)

SKILL_NAME = "supplier-checker"


def calculate_margin(
    sale_price: float,
    supplier_cost: float,
    shipping_cost: float,
    daily_budget: float,
    daily_orders: float,
) -> dict:
    """Calculate net margin with the exact dropshipping cost formula."""
    cost_per_order_ads = daily_budget / max(daily_orders, 0.1)
    shopify_fee = sale_price * 0.029 + 0.30
    refund_buffer = sale_price * 0.03
    total_cost = supplier_cost + shipping_cost + cost_per_order_ads + shopify_fee + refund_buffer
    net_margin_pct = (sale_price - total_cost) / sale_price if sale_price > 0 else 0.0
    return {
        "net_margin_pct": net_margin_pct,
        "net_margin_usd": sale_price - total_cost,
        "total_cost": total_cost,
        "breakdown": {
            "supplier": supplier_cost,
            "shipping": shipping_cost,
            "ads_per_order": cost_per_order_ads,
            "shopify_fee": round(shopify_fee, 2),
            "refund_buffer": round(refund_buffer, 2),
        },
    }


def _classify_margin(net_margin_pct: float) -> str:
    """Return flag color based on margin percentage."""
    if net_margin_pct > 0.30:
        return "green"
    elif net_margin_pct > 0.15:
        return "yellow"
    else:
        return "red"


def _build_recommendation(flag: str, net_margin_pct: float, net_margin_usd: float) -> str:
    pct = round(net_margin_pct * 100, 1)
    usd = round(net_margin_usd, 2)
    if flag == "green":
        return (
            f"Strong margin of {pct}% (${usd}/order). "
            "This product is highly viable for dropshipping."
        )
    elif flag == "yellow":
        return (
            f"Acceptable margin of {pct}% (${usd}/order). "
            "Viable but consider optimizing ad spend or negotiating supplier costs."
        )
    else:
        return (
            f"Low margin of {pct}% (${usd}/order). "
            "This product is not viable at current pricing. "
            "Consider raising the sale price or finding a cheaper supplier."
        )


class SupplierCheckerSkill(BaseSkill[SupplierCheckerInput, SupplierCheckerOutput]):
    name = SKILL_NAME
    version = "1.0.0"
    description = "Check supplier viability with margin calculation"
    consumes_credits = True
    credit_cost = 1

    def validate(self, input: SupplierCheckerInput) -> bool:
        if not input.product_title.strip():
            raise InvalidParamsError(
                message="product_title must not be empty",
                skill=SKILL_NAME,
                code="INVALID_PARAMS",
            )
        if input.sale_price <= 0:
            raise InvalidParamsError(
                message="sale_price must be positive",
                skill=SKILL_NAME,
                code="INVALID_PARAMS",
            )
        return True

    async def run(
        self, input: SupplierCheckerInput, ctx: SkillContext
    ) -> SkillResult[SupplierCheckerOutput]:
        start = time.perf_counter()
        self.validate(input)

        # ── Check cache ──────────────────────────────────────────────
        cache_params = input.model_dump()
        cached_data = await cache.get_cached(ctx.user_id, cache_params)
        if cached_data is not None:
            output = SupplierCheckerOutput(**cached_data)
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return SkillResult(
                success=True,
                data=output,
                cached=True,
                execution_ms=elapsed_ms,
            )

        # ── Find best supplier cost ──────────────────────────────────
        best_supplier_cost = input.supplier_cost
        best_supplier_source = "user_provided"
        alternative_suppliers: list[dict] = []

        if best_supplier_cost is None:
            # Try AliExpress first
            try:
                async with httpx.AsyncClient() as client:
                    products = await api_client.search_aliexpress(
                        client, input.product_title, limit=10
                    )
                if products:
                    # Sort by price and pick the cheapest
                    for p in products:
                        price = p.get("price", p.get("salePrice", p.get("sale_price")))
                        if price is not None:
                            try:
                                price_val = float(str(price).replace("$", "").replace(",", ""))
                            except (ValueError, TypeError):
                                continue
                            alternative_suppliers.append({
                                "source": "aliexpress",
                                "title": p.get("title", p.get("productTitle", "")),
                                "price_usd": price_val,
                                "url": p.get("url", p.get("productUrl", "")),
                            })

                    if alternative_suppliers:
                        alternative_suppliers.sort(key=lambda x: x["price_usd"])
                        best_supplier_cost = alternative_suppliers[0]["price_usd"]
                        best_supplier_source = "aliexpress"
            except (UpstreamError, Exception) as exc:
                logger.warning("AliExpress search failed: %s", exc)

            # Fallback to AI estimate if no AliExpress results
            if best_supplier_cost is None:
                try:
                    ai_estimate = await api_client.estimate_price_with_ai(input.product_title)
                    best_supplier_cost = ai_estimate.get("supplier_cost_usd", 0.0)
                    best_supplier_source = "ai_estimate"
                    alternative_suppliers.append({
                        "source": "ai_estimate",
                        "title": input.product_title,
                        "price_usd": best_supplier_cost,
                        "recommended_price": ai_estimate.get("recommended_price_usd"),
                        "market_avg": ai_estimate.get("market_avg_usd"),
                        "competition": ai_estimate.get("competition_level"),
                    })
                except Exception as exc:
                    logger.error("AI price estimation failed: %s", exc)
                    raise UpstreamError(
                        message="Could not determine supplier cost from any source",
                        skill=SKILL_NAME,
                        code="NO_SUPPLIER_DATA",
                    ) from exc

        # ── Calculate margin ─────────────────────────────────────────
        margin = calculate_margin(
            sale_price=input.sale_price,
            supplier_cost=best_supplier_cost,
            shipping_cost=input.shipping_cost,
            daily_budget=input.daily_budget_usd,
            daily_orders=input.daily_orders_estimate,
        )

        net_margin_pct = margin["net_margin_pct"]
        net_margin_usd = margin["net_margin_usd"]
        flag = _classify_margin(net_margin_pct)
        is_viable = net_margin_pct > 0.15
        recommendation = _build_recommendation(flag, net_margin_pct, net_margin_usd)

        output = SupplierCheckerOutput(
            product_title=input.product_title,
            sale_price=input.sale_price,
            best_supplier_cost=round(best_supplier_cost, 2),
            best_supplier_source=best_supplier_source,
            net_margin_pct=round(net_margin_pct, 4),
            net_margin_usd=round(net_margin_usd, 2),
            is_viable=is_viable,
            flag=flag,
            breakdown=margin["breakdown"],
            recommendation=recommendation,
            alternative_suppliers=alternative_suppliers,
        )

        # ── Cache result ─────────────────────────────────────────────
        await cache.set_cached(ctx.user_id, cache_params, output.model_dump())

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return SkillResult(
            success=True,
            data=output,
            cached=False,
            execution_ms=elapsed_ms,
        )
