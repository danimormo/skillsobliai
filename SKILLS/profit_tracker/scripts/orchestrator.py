"""Entry point for the profit-tracker skill.

`compute_profit()` fans out to Shopify + ad-platform clients in parallel,
normalises every money amount into the reporting currency, then hands the
aggregated facts to `pnl_builder.build_pnl`.

This module is the only one the parent agent imports.
"""
from __future__ import annotations

import asyncio
import logging
import os
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Iterable

from SKILLS.profit_tracker.scripts import (
    google_ads_client,
    meta_ads_client,
    processing_fees,
    shopify_client,
    tiktok_ads_client,
)
from SKILLS.profit_tracker.scripts.normalize import resolve_period
from SKILLS.profit_tracker.scripts.pnl_builder import (
    DailyChannelSpend,
    DailyPnLRow,
    DataQuality,
    Money,
    OrderFacts,
    Period,
    PlatformFees,
    ProcessorFees,
    ProfitReport,
    ZERO,
    build_pnl,
)

logger = logging.getLogger(__name__)

DEFAULT_CHANNELS = ("meta", "google", "tiktok", "shopify_apps")


async def compute_profit(
    *,
    store_id: str,
    period: Any,
    reporting_currency: str = "EUR",
    include: Iterable[str] = DEFAULT_CHANNELS,
    compare_previous: bool = False,
    credentials: dict | None = None,
) -> ProfitReport:
    """Produce the end-to-end P&L for a store over `period`.

    `credentials` is optional; when omitted the clients fall back to env
    vars (see `INTEGRATION.md`). The parent agent typically passes
    credentials loaded from its own secret store.
    """
    resolved_period = resolve_period(period)
    creds = _load_credentials(credentials)
    include_set = set(include)
    data_quality = DataQuality()

    # ── 1. Shopify (orders + transactions + app + plan fees) ──────────
    try:
        orders, transactions = await shopify_client.fetch_order_facts(
            shop_domain=creds["shopify_shop_domain"],
            admin_token=creds["shopify_admin_token"],
            period=resolved_period,
            reporting_currency=reporting_currency,
        )
    except Exception as exc:
        logger.exception("shopify fetch failed")
        raise

    app_fees_task = shopify_client.fetch_app_fees(
        shop_domain=creds["shopify_shop_domain"],
        admin_token=creds["shopify_admin_token"],
        period=resolved_period,
        reporting_currency=reporting_currency,
    )
    plan_fee_task = shopify_client.fetch_plan_fee(
        shop_domain=creds["shopify_shop_domain"],
        admin_token=creds["shopify_admin_token"],
        period=resolved_period,
        reporting_currency=reporting_currency,
        monthly_plan_cost=creds.get("shopify_plan_monthly_cost"),
    )
    payout_task = shopify_client.fetch_payout_net(
        shop_domain=creds["shopify_shop_domain"],
        admin_token=creds["shopify_admin_token"],
        period=resolved_period,
        reporting_currency=reporting_currency,
    )

    # ── 2. Ad channels in parallel ────────────────────────────────────
    ad_tasks: dict[str, asyncio.Task] = {}
    if "meta" in include_set and creds.get("meta_token"):
        ad_tasks["meta"] = asyncio.create_task(
            meta_ads_client.fetch_spend(
                access_token=creds["meta_token"],
                ad_account_id=creds["meta_ad_account_id"],
                period=resolved_period,
                reporting_currency=reporting_currency,
            )
        )
    if "google" in include_set and creds.get("google_refresh_token"):
        ad_tasks["google"] = asyncio.create_task(
            google_ads_client.fetch_spend(
                developer_token=creds["google_developer_token"],
                client_id=creds["google_client_id"],
                client_secret=creds["google_client_secret"],
                refresh_token=creds["google_refresh_token"],
                login_customer_id=creds["google_login_customer_id"],
                customer_id=creds["google_customer_id"],
                period=resolved_period,
                reporting_currency=reporting_currency,
            )
        )
    if "tiktok" in include_set and creds.get("tiktok_token"):
        ad_tasks["tiktok"] = asyncio.create_task(
            tiktok_ads_client.fetch_spend(
                access_token=creds["tiktok_token"],
                advertiser_id=creds["tiktok_advertiser_id"],
                period=resolved_period,
                reporting_currency=reporting_currency,
            )
        )

    daily_spend_by_channel: dict[str, list[DailyChannelSpend]] = {}
    for channel, task in ad_tasks.items():
        try:
            daily_spend_by_channel[channel] = await task
        except Exception as exc:
            logger.warning("channel %s failed: %s", channel, exc)
            data_quality.skipped_channels.append(channel)
            daily_spend_by_channel[channel] = []

    for channel in ("meta", "google", "tiktok"):
        if channel in include_set and channel not in ad_tasks:
            data_quality.skipped_channels.append(channel)

    ad_by_channel: dict[str, Money] = {}
    for channel, rows in daily_spend_by_channel.items():
        total = Money.zero(reporting_currency)
        for r in rows:
            total = total.add(r.spend)
        ad_by_channel[channel] = total

    # ── 3. Processing fees ────────────────────────────────────────────
    processor_fees = processing_fees.aggregate_processor_fees(
        transactions,
        reporting_currency=reporting_currency,
    )
    for bucket in processor_fees.estimated_flags:
        if bucket not in data_quality.estimated_channels:
            data_quality.estimated_channels.append(bucket)

    payout_net = None
    try:
        payout_net = await payout_task
    except Exception as exc:
        logger.warning("payout reconcile skipped: %s", exc)
    warn = processing_fees.reconcile(processor_fees, payout_net)
    if warn:
        data_quality.warnings.append(warn)

    # ── 4. Platform fees ──────────────────────────────────────────────
    app_fees = Money.zero(reporting_currency)
    plan_fee = Money.zero(reporting_currency)
    if "shopify_apps" in include_set:
        try:
            app_fees = await app_fees_task
        except Exception as exc:
            logger.warning("app fees failed: %s", exc)
            data_quality.skipped_channels.append("shopify_apps")
    else:
        app_fees_task.cancel()
    try:
        plan_fee = await plan_fee_task
    except Exception as exc:
        logger.warning("plan fee failed: %s", exc)

    transaction_fee = _shopify_transaction_fee(
        orders=orders,
        reporting_currency=reporting_currency,
        rate=Decimal("0.02"),
    )

    platform_fees = PlatformFees(
        shopify_plan=plan_fee,
        shopify_transaction=transaction_fee,
        app_fees=app_fees,
    )

    # ── 5. Daily time series ──────────────────────────────────────────
    daily_rows = _build_daily_rows(
        period=resolved_period,
        orders_daily=_bucket_orders_by_day(transactions, reporting_currency),
        spend_by_day=_bucket_spend_by_day(daily_spend_by_channel, reporting_currency),
        reporting_currency=reporting_currency,
    )

    # ── 6. Assemble ───────────────────────────────────────────────────
    report = build_pnl(
        store_id=store_id,
        period=resolved_period,
        reporting_currency=reporting_currency,
        orders=orders,
        processor_fees=processor_fees,
        ad_by_channel=ad_by_channel,
        platform_fees=platform_fees,
        daily_rows=daily_rows,
        data_quality=data_quality,
    )
    return report


# ─────────────────────────── helpers ──────────────────────────────────


def _load_credentials(overrides: dict | None) -> dict:
    overrides = overrides or {}
    env = os.environ
    return {
        "shopify_shop_domain": overrides.get("shopify_shop_domain", env.get("SHOPIFY_SHOP_DOMAIN", "")),
        "shopify_admin_token": overrides.get("shopify_admin_token", env.get("SHOPIFY_ADMIN_TOKEN", "")),
        "shopify_plan_monthly_cost": overrides.get("shopify_plan_monthly_cost"),
        "meta_token": overrides.get("meta_token", env.get("META_ACCESS_TOKEN")),
        "meta_ad_account_id": overrides.get("meta_ad_account_id", env.get("META_AD_ACCOUNT_ID", "")),
        "google_developer_token": overrides.get("google_developer_token", env.get("GOOGLE_ADS_DEVELOPER_TOKEN", "")),
        "google_client_id": overrides.get("google_client_id", env.get("GOOGLE_ADS_CLIENT_ID", "")),
        "google_client_secret": overrides.get("google_client_secret", env.get("GOOGLE_ADS_CLIENT_SECRET", "")),
        "google_refresh_token": overrides.get("google_refresh_token", env.get("GOOGLE_ADS_REFRESH_TOKEN")),
        "google_login_customer_id": overrides.get("google_login_customer_id", env.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "")),
        "google_customer_id": overrides.get("google_customer_id", env.get("GOOGLE_ADS_CUSTOMER_ID", "")),
        "tiktok_token": overrides.get("tiktok_token", env.get("TIKTOK_ACCESS_TOKEN")),
        "tiktok_advertiser_id": overrides.get("tiktok_advertiser_id", env.get("TIKTOK_ADVERTISER_ID", "")),
    }


def _shopify_transaction_fee(
    *, orders: OrderFacts, reporting_currency: str, rate: Decimal
) -> Money:
    non_sp_gross = Decimal("0")
    for gateway, money in (orders.by_processor or {}).items():
        if gateway == "shopify_payments":
            continue
        non_sp_gross += money.amount
    return Money(amount=non_sp_gross * rate, currency=reporting_currency)


def _bucket_spend_by_day(
    daily_spend_by_channel: dict[str, list[DailyChannelSpend]],
    reporting_currency: str,
) -> dict[date, Money]:
    out: dict[date, Money] = {}
    for rows in daily_spend_by_channel.values():
        for r in rows:
            prev = out.get(r.day, Money.zero(reporting_currency))
            out[r.day] = prev.add(r.spend)
    return out


def _bucket_orders_by_day(
    transactions: list[dict], reporting_currency: str
) -> dict[date, Money]:
    out: dict[date, Money] = defaultdict(lambda: Money.zero(reporting_currency))
    for tx in transactions:
        if tx.get("kind") == "refund":
            continue
        day = tx["day"]
        out[day] = out[day].add(tx["amount"])
    return dict(out)


def _build_daily_rows(
    *,
    period: Period,
    orders_daily: dict[date, Money],
    spend_by_day: dict[date, Money],
    reporting_currency: str,
) -> list[DailyPnLRow]:
    ccy = reporting_currency
    rows: list[DailyPnLRow] = []
    day = period.start
    while day <= period.end:
        gross = orders_daily.get(day, Money.zero(ccy))
        ad = spend_by_day.get(day, Money.zero(ccy))
        net = gross
        rows.append(
            DailyPnLRow(
                day=day,
                gross_revenue=gross.rounded(),
                net_revenue=net.rounded(),
                cogs=Money.zero(ccy),
                shipping_cost=Money.zero(ccy),
                processing_fees=Money.zero(ccy),
                ad_spend=ad.rounded(),
                net_profit=net.sub(ad).rounded(),
            )
        )
        day += timedelta(days=1)
    return rows
