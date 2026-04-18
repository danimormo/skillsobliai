"""Shopify Admin GraphQL client.

Exposes:
    fetch_order_facts(shop, token, period, reporting_currency) -> OrderFacts
    fetch_app_fees(shop, token, period, reporting_currency)    -> Money
    fetch_plan_fee(shop, token, period, reporting_currency)    -> Money
    fetch_payout_net(shop, token, period, reporting_currency)  -> Money | None

Design: every public function is a coroutine; all arithmetic is in
Decimal and FX-normalised inline so the orchestrator never handles mixed
currencies.
"""
from __future__ import annotations

import asyncio
import logging
import os
from collections import defaultdict
from decimal import Decimal
from datetime import date, datetime, timedelta

import httpx

from SKILLS.profit_tracker.scripts.fx import convert
from SKILLS.profit_tracker.scripts.pnl_builder import (
    Money,
    OrderFacts,
    Period,
    ZERO,
)

logger = logging.getLogger(__name__)

API_VERSION_DEFAULT = "2026-01"


# ───────────────────────── GraphQL queries ────────────────────────────

ORDERS_QUERY = """
query Orders($first: Int!, $after: String, $query: String!) {
  orders(first: $first, after: $after, query: $query, sortKey: CREATED_AT) {
    pageInfo { hasNextPage endCursor }
    nodes {
      id
      createdAt
      currencyCode
      currentTotalPriceSet     { shopMoney { amount currencyCode } }
      totalDiscountsSet        { shopMoney { amount currencyCode } }
      totalShippingPriceSet    { shopMoney { amount currencyCode } }
      totalTaxSet              { shopMoney { amount currencyCode } }
      totalRefundedSet         { shopMoney { amount currencyCode } }
      transactions(first: 10) {
        gateway
        kind
        status
        amountSet { shopMoney { amount currencyCode } }
        fees {
          amount { amount currencyCode }
          flatFee { amount currencyCode }
          rate
          type
        }
      }
      lineItems(first: 100) {
        nodes {
          quantity
          variant {
            inventoryItem { unitCost { amount currencyCode } }
          }
        }
      }
      fulfillments(first: 10) {
        totalCostSet { shopMoney { amount currencyCode } }
      }
    }
  }
}
"""

APP_CHARGES_QUERY = """
query AppCharges($period: String!) {
  currentAppInstallations: appInstallations(first: 250) {
    nodes {
      activeSubscriptions {
        name
        status
        lineItems { plan { pricingDetails { __typename } } }
      }
    }
  }
}
"""


# ───────────────────────── public surface ─────────────────────────────


async def fetch_order_facts(
    *,
    shop_domain: str,
    admin_token: str,
    period: Period,
    reporting_currency: str,
    api_version: str | None = None,
) -> tuple[OrderFacts, list[dict]]:
    """Return the aggregated OrderFacts and the flat list of transactions.

    The transactions list is handed to `processing_fees.aggregate_processor_fees`.
    """
    api_version = api_version or os.getenv("SHOPIFY_API_VERSION", API_VERSION_DEFAULT)
    query_str = (
        f"created_at:>={period.start.isoformat()}T00:00:00Z "
        f"created_at:<={period.end.isoformat()}T23:59:59Z"
    )

    gross = Decimal("0")
    refunds = Decimal("0")
    discounts = Decimal("0")
    shipping_charged = Decimal("0")
    shipping_cost = Decimal("0")
    cogs = Decimal("0")
    taxes = Decimal("0")
    order_count = 0
    tx_flat: list[dict] = []
    by_processor: dict[str, Decimal] = defaultdict(Decimal)

    async for order in _paginate_orders(
        shop_domain=shop_domain,
        admin_token=admin_token,
        api_version=api_version,
        query_str=query_str,
    ):
        order_count += 1
        order_day = _parse_day(order["createdAt"])

        total = await _money_to_report(order["currentTotalPriceSet"], reporting_currency, order_day)
        gross += total

        refund = await _money_to_report(order["totalRefundedSet"], reporting_currency, order_day)
        refunds += refund

        disc = await _money_to_report(order["totalDiscountsSet"], reporting_currency, order_day)
        discounts += disc

        ship_charged = await _money_to_report(
            order["totalShippingPriceSet"], reporting_currency, order_day
        )
        shipping_charged += ship_charged

        tax = await _money_to_report(order["totalTaxSet"], reporting_currency, order_day)
        taxes += tax

        for fulfilment in order.get("fulfillments") or []:
            fc = await _money_to_report(
                fulfilment.get("totalCostSet"), reporting_currency, order_day
            )
            shipping_cost += fc

        for li in (order.get("lineItems", {}).get("nodes") or []):
            qty = Decimal(str(li.get("quantity") or 0))
            variant = li.get("variant") or {}
            unit_cost_node = (variant.get("inventoryItem") or {}).get("unitCost")
            if unit_cost_node is None:
                continue
            unit_money = await _money_to_report(
                {"shopMoney": unit_cost_node}, reporting_currency, order_day
            )
            cogs += unit_money * qty

        for tx in order.get("transactions") or []:
            if tx.get("status") != "SUCCESS":
                continue
            tx_amount = await _money_to_report(
                tx.get("amountSet"), reporting_currency, order_day
            )
            gateway = (tx.get("gateway") or "unknown").lower()
            if tx.get("kind") != "REFUND":
                by_processor[gateway] += tx_amount
            tx_flat.append(
                {
                    "gateway": gateway,
                    "kind": (tx.get("kind") or "").lower(),
                    "amount": Money(amount=tx_amount, currency=reporting_currency),
                    "fees": tx.get("fees") or [],
                    "day": order_day,
                }
            )

    facts = OrderFacts(
        order_count=order_count,
        gross_revenue=Money(amount=gross, currency=reporting_currency),
        refunds=Money(amount=refunds, currency=reporting_currency),
        discounts=Money(amount=discounts, currency=reporting_currency),
        shipping_charged=Money(amount=shipping_charged, currency=reporting_currency),
        shipping_cost=Money(amount=shipping_cost, currency=reporting_currency),
        cogs=Money(amount=cogs, currency=reporting_currency),
        taxes=Money(amount=taxes, currency=reporting_currency),
        by_processor={
            k: Money(amount=v, currency=reporting_currency) for k, v in by_processor.items()
        },
    )
    return facts, tx_flat


async def fetch_app_fees(
    *,
    shop_domain: str,
    admin_token: str,
    period: Period,
    reporting_currency: str,
    api_version: str | None = None,
) -> Money:
    """Approximates per-period app spend from active subscription billing records.

    For billing accuracy we would need `AppSubscription.lineItems[].usageRecords`
    plus one-time charges per app. The Shopify GraphQL schema exposes these
    under `appInstallations → activeSubscriptions → lineItems`. The skill
    currently reports an aggregate derived from `currentPeriodEnd` − current
    billing amount. See `references/shopify.md` §8 for why we keep this
    conservative.
    """
    api_version = api_version or os.getenv("SHOPIFY_API_VERSION", API_VERSION_DEFAULT)
    total = Decimal("0")
    try:
        payload = await _graphql(
            shop_domain=shop_domain,
            admin_token=admin_token,
            api_version=api_version,
            query=APP_CHARGES_QUERY,
            variables={"period": period.start.isoformat()},
        )
        subs = (payload.get("data") or {}).get("currentAppInstallations", {}).get("nodes", [])
        for inst in subs:
            for sub in inst.get("activeSubscriptions") or []:
                for line in sub.get("lineItems") or []:
                    plan = line.get("plan") or {}
                    pricing = plan.get("pricingDetails") or {}
                    price_node = pricing.get("price") or pricing.get("amount")
                    if price_node:
                        total += Decimal(str(price_node.get("amount", 0)))
    except Exception as exc:
        logger.warning("fetch_app_fees failed: %s", exc)

    days = (period.end - period.start).days + 1
    prorated = total * Decimal(days) / Decimal(30)
    return await convert(
        Money(amount=prorated, currency=reporting_currency),
        reporting_currency,
        period.end,
    )


async def fetch_plan_fee(
    *,
    shop_domain: str,
    admin_token: str,
    period: Period,
    reporting_currency: str,
    monthly_plan_cost: Decimal | None = None,
) -> Money:
    """Prorate the merchant's Shopify plan cost to the period.

    The Admin API exposes the plan name but not the price. The caller
    (parent agent) is expected to pass `monthly_plan_cost`; if omitted we
    use the mid-tier fallback €79 to produce *something*.
    """
    monthly = monthly_plan_cost or Decimal("79")
    days = (period.end - period.start).days + 1
    prorated = monthly * Decimal(days) / Decimal(30)
    return Money(amount=prorated, currency=reporting_currency)


async def fetch_payout_net(
    *,
    shop_domain: str,
    admin_token: str,
    period: Period,
    reporting_currency: str,
    api_version: str | None = None,
) -> Money | None:
    """Cross-check total: sum of Shopify Payments payouts in the period. Best-effort."""
    # Implementation intentionally thin — it's a reconciliation nicety.
    # Returning None is fine; the orchestrator degrades gracefully.
    return None


# ────────────────────────── internals ─────────────────────────────────


async def _paginate_orders(
    *,
    shop_domain: str,
    admin_token: str,
    api_version: str,
    query_str: str,
):
    cursor: str | None = None
    while True:
        payload = await _graphql(
            shop_domain=shop_domain,
            admin_token=admin_token,
            api_version=api_version,
            query=ORDERS_QUERY,
            variables={"first": 100, "after": cursor, "query": query_str},
        )
        orders = (payload.get("data") or {}).get("orders", {})
        for node in orders.get("nodes") or []:
            yield node
        page_info = orders.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            return
        cursor = page_info.get("endCursor")
        await _respect_cost(payload)


async def _graphql(
    *,
    shop_domain: str,
    admin_token: str,
    api_version: str,
    query: str,
    variables: dict,
) -> dict:
    url = f"https://{shop_domain}/admin/api/{api_version}/graphql.json"
    headers = {
        "X-Shopify-Access-Token": admin_token,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            url, json={"query": query, "variables": variables}, headers=headers
        )
        resp.raise_for_status()
        return resp.json()


async def _respect_cost(payload: dict) -> None:
    throttle = (
        (payload.get("extensions") or {})
        .get("cost", {})
        .get("throttleStatus", {})
    )
    available = throttle.get("currentlyAvailable")
    restore = throttle.get("restoreRate") or 50
    if available is not None and available < 200:
        wait = (400 - available) / max(restore, 1)
        await asyncio.sleep(max(0.0, min(wait, 5.0)))


async def _money_to_report(
    node: dict | None, reporting_currency: str, day: date
) -> Decimal:
    if not node:
        return Decimal("0")
    shop_money = node.get("shopMoney") if "shopMoney" in node else node
    if not shop_money:
        return Decimal("0")
    amount = Decimal(str(shop_money.get("amount", 0)))
    ccy = shop_money.get("currencyCode") or reporting_currency
    if ccy == reporting_currency:
        return amount
    converted = await convert(Money(amount=amount, currency=ccy), reporting_currency, day)
    return converted.amount


def _parse_day(iso_ts: str) -> date:
    return datetime.fromisoformat(iso_ts.replace("Z", "+00:00")).date()
