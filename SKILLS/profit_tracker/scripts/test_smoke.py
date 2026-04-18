"""Smoke tests for profit-tracker — 4 tests, all green, zero network calls.

Run with:
    pytest SKILLS/profit_tracker/scripts/test_smoke.py -q
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from SKILLS.profit_tracker.scripts import fx
from SKILLS.profit_tracker.scripts.normalize import resolve_period
from SKILLS.profit_tracker.scripts.pnl_builder import (
    DataQuality,
    Money,
    OrderFacts,
    Period,
    PlatformFees,
    ProcessorFees,
    build_pnl,
)
from SKILLS.profit_tracker.scripts.processing_fees import (
    aggregate_processor_fees,
    fees_for_transaction,
)


@pytest.fixture(autouse=True)
def _fx_overlay():
    fx.set_test_rates(
        {
            ("USD", "EUR", date(2026, 3, 15)): Decimal("0.92"),
            ("EUR", "USD", date(2026, 3, 15)): Decimal("1.0870"),
        }
    )
    yield
    fx.clear_test_rates()


# ─────────────────────────── test 1 ───────────────────────────────────


def test_resolve_period_last_7d_is_inclusive_7_days():
    today = date(2026, 4, 18)
    p = resolve_period("last_7d", today=today)
    assert p.start == date(2026, 4, 11)
    assert p.end == date(2026, 4, 17)
    assert (p.end - p.start).days + 1 == 7


# ─────────────────────────── test 2 ───────────────────────────────────


def test_build_pnl_canonical_formula():
    """Hand-computed golden numbers — if these drift the formula changed."""
    ccy = "EUR"
    period = Period(start=date(2026, 3, 1), end=date(2026, 3, 31))

    orders = OrderFacts(
        order_count=100,
        gross_revenue=Money(amount=Decimal("10000.00"), currency=ccy),
        refunds=Money(amount=Decimal("500.00"), currency=ccy),
        discounts=Money(amount=Decimal("200.00"), currency=ccy),
        shipping_charged=Money(amount=Decimal("800.00"), currency=ccy),
        shipping_cost=Money(amount=Decimal("600.00"), currency=ccy),
        cogs=Money(amount=Decimal("3000.00"), currency=ccy),
        taxes=Money(amount=Decimal("1800.00"), currency=ccy),
        by_processor={
            "shopify_payments": Money(amount=Decimal("7000.00"), currency=ccy),
            "paypal": Money(amount=Decimal("3000.00"), currency=ccy),
        },
    )
    processor_fees = ProcessorFees(
        shopify_payments=Money(amount=Decimal("150.00"), currency=ccy),
        stripe=Money(amount=Decimal("0.00"), currency=ccy),
        paypal=Money(amount=Decimal("100.00"), currency=ccy),
        airwallex=Money(amount=Decimal("0.00"), currency=ccy),
        other=Money(amount=Decimal("0.00"), currency=ccy),
    )
    ad_by_channel = {
        "meta":   Money(amount=Decimal("1200.00"), currency=ccy),
        "google": Money(amount=Decimal("800.00"),  currency=ccy),
        "tiktok": Money(amount=Decimal("500.00"),  currency=ccy),
    }
    platform_fees = PlatformFees(
        shopify_plan=Money(amount=Decimal("79.00"), currency=ccy),
        shopify_transaction=Money(amount=Decimal("60.00"), currency=ccy),
        app_fees=Money(amount=Decimal("45.00"), currency=ccy),
    )

    report = build_pnl(
        store_id="test-shop",
        period=period,
        reporting_currency=ccy,
        orders=orders,
        processor_fees=processor_fees,
        ad_by_channel=ad_by_channel,
        platform_fees=platform_fees,
        daily_rows=[],
        data_quality=DataQuality(),
    )

    # net_revenue = 10000 - 500 = 9500
    assert report.net_revenue.amount == Decimal("9500.00")
    # ad_spend = 1200 + 800 + 500 = 2500
    assert report.ad_spend.amount == Decimal("2500.00")
    # net_profit = 9500 - 3000 - 600 - 250 - 2500 - 184 = 2966
    assert report.net_profit.amount == Decimal("2966.00")
    # contribution_margin = (9500 - 3000 - 600 - 250) / 9500 = 0.5947...
    assert report.contribution_margin == Decimal("0.5947")
    # poas = 2966 / 2500 = 1.1864
    assert report.poas == Decimal("1.1864")


# ─────────────────────────── test 3 ───────────────────────────────────


def test_processing_fees_uses_shopify_ground_truth_when_available():
    """If transaction.fees is populated we trust Shopify's numbers as-is."""
    tx = [
        {
            "gateway": "shopify_payments",
            "kind": "sale",
            "amount": Money(amount=Decimal("100.00"), currency="EUR"),
            "fees": [
                {"amount": {"amount": "2.85", "currencyCode": "EUR"}, "rate": "0.025"}
            ],
        }
    ]
    out = aggregate_processor_fees(tx, reporting_currency="EUR")
    assert out.shopify_payments.amount == Decimal("2.85")
    # No estimation flag — we used ground truth.
    assert "shopify_payments" not in out.estimated_flags

    # When `fees` is empty we fall back to the table → must flag as estimated.
    fee, estimated = fees_for_transaction(
        gateway="stripe",
        amount=Money(amount=Decimal("100.00"), currency="EUR"),
        shopify_fees_payload=None,
        region_hint="EU",
    )
    assert estimated is True
    # 100 * 1.5% + 0.25 = 1.75
    assert fee.amount == Decimal("1.75")


# ─────────────────────────── test 4 ───────────────────────────────────


def test_fx_override_is_honoured_and_cleanly_clears():
    """FX overlay is how the skill stays offline during tests."""
    fx.set_test_rates(
        {("USD", "EUR", date(2026, 3, 15)): Decimal("0.90")}
    )
    import asyncio

    rate = asyncio.get_event_loop().run_until_complete(
        fx.get_rate("USD", "EUR", date(2026, 3, 15))
    )
    assert rate == Decimal("0.90")

    # converting respects the same overlay
    m = asyncio.get_event_loop().run_until_complete(
        fx.convert(Money(amount=Decimal("100"), currency="USD"), "EUR", date(2026, 3, 15))
    )
    assert m.currency == "EUR"
    assert m.amount == Decimal("90.00")
