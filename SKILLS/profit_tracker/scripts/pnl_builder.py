"""Core P&L math. No network, no I/O, no framework dependencies.

This module is the single source of truth for the profit formula. The
`SKILL.md` doc mirrors it; if the two disagree, this file wins.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Literal

from pydantic import BaseModel, Field

ZERO = Decimal("0")
TWO_DP = Decimal("0.01")


# ─────────────────────────── models ───────────────────────────────────


class Money(BaseModel):
    amount: Decimal = Field(default=ZERO)
    currency: str

    @classmethod
    def zero(cls, currency: str) -> "Money":
        return cls(amount=ZERO, currency=currency)

    def add(self, other: "Money") -> "Money":
        if other.currency != self.currency:
            raise ValueError(
                f"cannot add {self.currency} and {other.currency} without fx"
            )
        return Money(amount=self.amount + other.amount, currency=self.currency)

    def sub(self, other: "Money") -> "Money":
        if other.currency != self.currency:
            raise ValueError(
                f"cannot subtract {self.currency} and {other.currency} without fx"
            )
        return Money(amount=self.amount - other.amount, currency=self.currency)

    def rounded(self) -> "Money":
        return Money(
            amount=self.amount.quantize(TWO_DP, rounding=ROUND_HALF_EVEN),
            currency=self.currency,
        )


class Period(BaseModel):
    start: date
    end: date
    tz: str = "Europe/Rome"


class DailyChannelSpend(BaseModel):
    channel: Literal["meta", "google", "tiktok"]
    day: date
    spend: Money
    impressions: int = 0
    clicks: int = 0
    purchases: int = 0
    revenue: Money | None = None
    attribution_note: str | None = None


class OrderFacts(BaseModel):
    order_count: int = 0
    gross_revenue: Money
    refunds: Money
    discounts: Money
    shipping_charged: Money
    shipping_cost: Money
    cogs: Money
    taxes: Money
    by_processor: dict[str, Money] = Field(default_factory=dict)


class ProcessorFees(BaseModel):
    shopify_payments: Money
    stripe: Money
    paypal: Money
    airwallex: Money
    other: Money
    estimated_flags: dict[str, bool] = Field(default_factory=dict)

    def total(self) -> Money:
        ccy = self.shopify_payments.currency
        total = Money.zero(ccy)
        for m in (
            self.shopify_payments,
            self.stripe,
            self.paypal,
            self.airwallex,
            self.other,
        ):
            total = total.add(m)
        return total


class PlatformFees(BaseModel):
    shopify_plan: Money
    shopify_transaction: Money
    app_fees: Money

    def total(self) -> Money:
        return self.shopify_plan.add(self.shopify_transaction).add(self.app_fees)


class DataQuality(BaseModel):
    estimated_channels: list[str] = Field(default_factory=list)
    skipped_channels: list[str] = Field(default_factory=list)
    fx_fallback_days: list[date] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DailyPnLRow(BaseModel):
    day: date
    gross_revenue: Money
    net_revenue: Money
    cogs: Money
    shipping_cost: Money
    processing_fees: Money
    ad_spend: Money
    net_profit: Money


class ProfitReport(BaseModel):
    store_id: str
    period: Period
    reporting_currency: str

    gross_revenue: Money
    refunds: Money
    discounts: Money
    net_revenue: Money

    cogs: Money
    shipping_cost: Money
    processing_fees: ProcessorFees
    ad_spend: Money
    ad_by_channel: dict[str, Money]
    platform_fees: PlatformFees

    net_profit: Money
    contribution_margin: Decimal
    mer: Decimal | None
    nc_roas: Decimal | None
    poas: Decimal | None

    daily: list[DailyPnLRow]
    data_quality: DataQuality
    generated_at: datetime


# ─────────────────────────── core math ────────────────────────────────


def _safe_div(num: Decimal, den: Decimal) -> Decimal | None:
    if den == ZERO:
        return None
    return num / den


def build_pnl(
    *,
    store_id: str,
    period: Period,
    reporting_currency: str,
    orders: OrderFacts,
    processor_fees: ProcessorFees,
    ad_by_channel: dict[str, Money],
    platform_fees: PlatformFees,
    daily_rows: list[DailyPnLRow],
    data_quality: DataQuality,
) -> ProfitReport:
    """Assemble a ProfitReport from already-normalised inputs.

    All `Money` inputs MUST already be in `reporting_currency`; FX happens
    upstream in `normalize.py`. This function is pure and synchronous so
    it can be unit-tested without any mocks.
    """
    ccy = reporting_currency

    gross_revenue = orders.gross_revenue
    refunds = orders.refunds
    discounts = orders.discounts
    net_revenue = gross_revenue.sub(refunds)

    cogs = orders.cogs
    shipping_cost = orders.shipping_cost
    processing_total = processor_fees.total()

    ad_spend = Money.zero(ccy)
    for m in ad_by_channel.values():
        ad_spend = ad_spend.add(m)

    platform_total = platform_fees.total()

    net_profit = (
        net_revenue
        .sub(cogs)
        .sub(shipping_cost)
        .sub(processing_total)
        .sub(ad_spend)
        .sub(platform_total)
    )

    contribution_num = (
        net_revenue.amount - cogs.amount - shipping_cost.amount - processing_total.amount
    )
    contribution_margin = _safe_div(contribution_num, net_revenue.amount) or ZERO

    mer = _safe_div(gross_revenue.amount, ad_spend.amount)
    nc_roas = _safe_div(net_revenue.amount, ad_spend.amount)
    poas = _safe_div(net_profit.amount, ad_spend.amount)

    return ProfitReport(
        store_id=store_id,
        period=period,
        reporting_currency=ccy,
        gross_revenue=gross_revenue.rounded(),
        refunds=refunds.rounded(),
        discounts=discounts.rounded(),
        net_revenue=net_revenue.rounded(),
        cogs=cogs.rounded(),
        shipping_cost=shipping_cost.rounded(),
        processing_fees=processor_fees,
        ad_spend=ad_spend.rounded(),
        ad_by_channel={k: v.rounded() for k, v in ad_by_channel.items()},
        platform_fees=platform_fees,
        net_profit=net_profit.rounded(),
        contribution_margin=contribution_margin.quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_EVEN
        ),
        mer=mer.quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN) if mer is not None else None,
        nc_roas=nc_roas.quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN) if nc_roas is not None else None,
        poas=poas.quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN) if poas is not None else None,
        daily=daily_rows,
        data_quality=data_quality,
        generated_at=datetime.now(timezone.utc),
    )
