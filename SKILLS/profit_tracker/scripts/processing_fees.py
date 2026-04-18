"""Payment-processor fee computation.

Ground truth for Shopify Payments: the `fees` array on each transaction
(Admin API v2023-07+). For every other processor we apply the fallback
tables documented in `references/payment_processors.md`.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from SKILLS.profit_tracker.scripts.pnl_builder import Money, ProcessorFees, ZERO

# ─────────────────────────── fee tables ───────────────────────────────
# Rates are (percentage, fixed_fee). Fixed fees are expressed in the
# gateway's "home" currency; callers must have FX-normalised the amount
# before calling us (or pass the currency-matched fixed fee).

STRIPE_TABLE: dict[str, tuple[Decimal, Decimal]] = {
    "EU":   (Decimal("0.015"), Decimal("0.25")),   # EU domestic
    "UK":   (Decimal("0.015"), Decimal("0.20")),
    "US":   (Decimal("0.029"), Decimal("0.30")),
    "NON_EEA": (Decimal("0.025"), Decimal("0.25")),
}

PAYPAL_TABLE: dict[str, tuple[Decimal, Decimal]] = {
    "EU_DOMESTIC": (Decimal("0.0249"), Decimal("0.35")),
    "EEA":         (Decimal("0.0299"), Decimal("0.00")),
    "INTL":        (Decimal("0.0499"), Decimal("0.00")),
}

AIRWALLEX_TABLE: dict[str, tuple[Decimal, Decimal]] = {
    "LOCAL":    (Decimal("0.014"), Decimal("0.20")),
    "PREMIUM":  (Decimal("0.019"), Decimal("0.20")),
    "INTL":     (Decimal("0.027"), Decimal("0.20")),
}

SHOPIFY_PAYMENTS_FALLBACK: dict[str, tuple[Decimal, Decimal]] = {
    # used only when `transaction.fees` is empty (rare)
    "EU": (Decimal("0.016"), Decimal("0.25")),
    "UK": (Decimal("0.015"), Decimal("0.20")),
    "US": (Decimal("0.029"), Decimal("0.30")),
}

UNKNOWN_GATEWAY_RATE = Decimal("0.025")


# ───────────────────────── per-transaction API ────────────────────────


def fees_for_transaction(
    *,
    gateway: str,
    amount: Money,
    shopify_fees_payload: list[dict] | None,
    region_hint: str = "EU",
) -> tuple[Money, bool]:
    """Return (fee, estimated_flag) for a single transaction.

    `shopify_fees_payload` is the `transaction.fees[]` array from the
    Shopify GraphQL response; non-empty iff gateway is Shopify Payments
    on a recent API version. When present it's ground truth and we sum
    it as-is.
    """
    if shopify_fees_payload:
        total = Decimal("0")
        ccy = amount.currency
        for f in shopify_fees_payload:
            node = f.get("amount") or f.get("fee") or {}
            val = node.get("amount") if isinstance(node, dict) else None
            if val is not None:
                total += Decimal(str(val))
                fee_ccy = node.get("currencyCode") if isinstance(node, dict) else None
                if fee_ccy:
                    ccy = fee_ccy
        return Money(amount=total, currency=ccy), False

    pct, fixed = _lookup_table(gateway, region_hint)
    fee_amount = (amount.amount * pct) + fixed
    estimated = True
    return Money(amount=fee_amount, currency=amount.currency), estimated


def _lookup_table(gateway: str, region_hint: str) -> tuple[Decimal, Decimal]:
    gateway = (gateway or "").lower()
    if gateway in ("shopify_payments", "bogus"):
        return SHOPIFY_PAYMENTS_FALLBACK.get(region_hint, SHOPIFY_PAYMENTS_FALLBACK["EU"])
    if gateway == "stripe":
        return STRIPE_TABLE.get(region_hint, STRIPE_TABLE["EU"])
    if gateway == "paypal":
        return PAYPAL_TABLE.get(region_hint, PAYPAL_TABLE["EU_DOMESTIC"])
    if gateway == "airwallex":
        return AIRWALLEX_TABLE.get(region_hint, AIRWALLEX_TABLE["LOCAL"])
    return (UNKNOWN_GATEWAY_RATE, Decimal("0"))


# ─────────────────────── aggregation over orders ──────────────────────


def aggregate_processor_fees(
    transactions: Iterable[dict],
    *,
    reporting_currency: str,
    region_hint: str = "EU",
) -> ProcessorFees:
    """Bucket per-transaction fees into the canonical processor columns.

    Each `transactions` element is expected to have shape:
        {
            "gateway":  str,
            "kind":     "sale" | "refund" | "capture" | ...,
            "amount":   Money,                        # already in reporting_currency
            "fees":     list[dict] | None,            # Shopify payload or None
        }
    """
    ccy = reporting_currency
    totals: dict[str, Decimal] = {
        "shopify_payments": Decimal("0"),
        "stripe": Decimal("0"),
        "paypal": Decimal("0"),
        "airwallex": Decimal("0"),
        "other": Decimal("0"),
    }
    estimated_flags: dict[str, bool] = {}

    for tx in transactions:
        if tx.get("kind") == "refund":
            continue
        gateway = (tx.get("gateway") or "").lower()
        fee, was_estimated = fees_for_transaction(
            gateway=gateway,
            amount=tx["amount"],
            shopify_fees_payload=tx.get("fees"),
            region_hint=region_hint,
        )
        bucket = _bucket_for_gateway(gateway)
        totals[bucket] += fee.amount
        if was_estimated:
            estimated_flags[bucket] = True

    return ProcessorFees(
        shopify_payments=Money(amount=totals["shopify_payments"], currency=ccy),
        stripe=Money(amount=totals["stripe"], currency=ccy),
        paypal=Money(amount=totals["paypal"], currency=ccy),
        airwallex=Money(amount=totals["airwallex"], currency=ccy),
        other=Money(amount=totals["other"], currency=ccy),
        estimated_flags=estimated_flags,
    )


def _bucket_for_gateway(gateway: str) -> str:
    if gateway in ("shopify_payments",):
        return "shopify_payments"
    if gateway == "stripe":
        return "stripe"
    if gateway == "paypal":
        return "paypal"
    if gateway == "airwallex":
        return "airwallex"
    return "other"


def reconcile(computed: ProcessorFees, payout_net: Money | None) -> str | None:
    """Return a warning string if computed fees disagree with actual payout by >1 %."""
    if payout_net is None:
        return None
    computed_total = computed.total().amount
    if computed_total == ZERO:
        return None
    delta = (computed_total - payout_net.amount).copy_abs() / computed_total
    if delta > Decimal("0.01"):
        return (
            f"processing fees drift {float(delta):.2%} vs Shopify Payments payout — "
            "review references/payment_processors.md"
        )
    return None
