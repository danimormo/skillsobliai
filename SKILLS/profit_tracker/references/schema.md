# Internal schema

All types live in `scripts/pnl_builder.py` (the only file that both the
orchestrator and the tests import models from). They are pydantic v2 models
so the parent agent can serialize them freely.

---

## `Period`

```python
class Period(BaseModel):
    start: date            # inclusive
    end:   date            # inclusive
    tz:    str = "Europe/Rome"
```

The orchestrator always works on inclusive-inclusive day boundaries. All
external APIs get their native format (Shopify wants ISO-8601, Meta wants
`{"since":"YYYY-MM-DD","until":"YYYY-MM-DD"}`, etc.) — conversion happens in
each client.

---

## `Money`

```python
class Money(BaseModel):
    amount:   Decimal     # always positive; direction is carried by the field name
    currency: str         # ISO-4217, e.g. "EUR"
```

- Use `Decimal`, never `float`, for anything that touches cash.
- `Money(amount=Decimal("0"), currency=reporting_currency)` is the zero
  value; never pass `None`.

---

## `DailyChannelSpend`

```python
class DailyChannelSpend(BaseModel):
    channel: Literal["meta", "google", "tiktok"]
    day:     date
    spend:   Money
    impressions: int = 0
    clicks:      int = 0
    purchases:   int = 0
    revenue:     Money | None = None   # platform-attributed, for sanity only
```

Only `spend` feeds the P&L. `revenue` on this object is platform-attributed
(i.e. what Meta/Google/TikTok *claim* you earned) and is carried through to
the report for diagnostics — the P&L always uses Shopify as source of truth
for revenue.

---

## `OrderFacts`

Flat, pre-aggregated view of Shopify orders for a period.

```python
class OrderFacts(BaseModel):
    order_count:        int
    gross_revenue:      Money     # Σ order.total_price
    refunds:            Money     # Σ refund.amount
    discounts:          Money     # Σ order.total_discounts (informational)
    shipping_charged:   Money     # Σ order.total_shipping_price_set (what customer paid)
    shipping_cost:      Money     # Σ fulfillment.shipping_cost (what carrier billed)
    cogs:               Money     # Σ line.quantity × variant.cost
    taxes:              Money     # Σ order.total_tax (informational only — we don't net)
    by_processor:       dict[str, Money]    # gross charged per processor (for fee calc)
```

**Note 1 — discounts:** `order.total_price` in Shopify is already net of
discounts. We still expose `discounts` separately so the parent agent can
answer "how much did promos cost me" without a second call.

**Note 2 — shipping:** we carry both what the customer paid *and* what the
carrier billed. The P&L uses the carrier-billed number as a cost. The
customer-paid number already lives inside `gross_revenue`.

---

## `ProcessorFees`

```python
class ProcessorFees(BaseModel):
    shopify_payments: Money
    stripe:           Money
    paypal:           Money
    airwallex:        Money
    other:            Money
    estimated_flags:  dict[str, bool]   # {"paypal": True} if we stimated this row
```

Estimation happens when the processor's own payout API is unavailable — see
`references/payment_processors.md`. Anything flagged `True` must show up in
`ProfitReport.data_quality.estimated_channels`.

---

## `PlatformFees`

```python
class PlatformFees(BaseModel):
    shopify_plan:         Money     # monthly plan cost, prorated to period
    shopify_transaction:  Money     # 0.5–2% on non-Shopify-Payments orders
    app_fees:             Money     # Σ billing_attempts for the period
```

---

## `ProfitReport`

Top-level return of `compute_profit`.

```python
class ProfitReport(BaseModel):
    store_id:            str
    period:              Period
    reporting_currency:  str

    gross_revenue:       Money
    refunds:             Money
    discounts:           Money
    net_revenue:         Money

    cogs:                Money
    shipping_cost:       Money
    processing_fees:     ProcessorFees
    ad_spend:            Money                 # Σ of ad_by_channel
    ad_by_channel:       dict[str, Money]
    platform_fees:       PlatformFees

    net_profit:          Money
    contribution_margin: Decimal               # fraction, not %
    mer:                 Decimal | None
    nc_roas:             Decimal | None
    poas:                Decimal | None

    daily:               list[DailyPnLRow]     # one row per day in period
    data_quality:        DataQuality
    generated_at:        datetime
```

---

## `DailyPnLRow`

One row per day of the period. Same shape as `ProfitReport` but with a
`date` field and no `data_quality` / `generated_at`.

---

## `DataQuality`

```python
class DataQuality(BaseModel):
    estimated_channels:  list[str]   # e.g. ["paypal", "airwallex"]
    skipped_channels:    list[str]   # integration missing or hard-failed
    fx_fallback_days:    list[date]  # days we couldn't get an ECB rate
    warnings:            list[str]   # free-form
```

The parent agent should always surface `warnings` verbatim to the user if
any are non-empty — silent estimation is a trust bug.
