---
name: profit-tracker
version: 1.0.0
description: Triple-Whale-style profit & loss tracker for a Shopify store. Automatically aggregates gross revenue, refunds, discounts, COGS, shipping, payment-processor fees, ad spend (Meta/Google/TikTok), Shopify subscription + app fees and FX-normalizes everything to a single reporting currency.
owner: growth-stack
---

# Profit Tracker

A skill that, given a reporting period and a store, answers one question only:

> **"How much did I actually make?"**

It is designed to be mounted as a sub-skill on a parent agent (see
`INTEGRATION.md`). It does not expose UI — only a single Python entry
point and a set of reference documents the parent agent can `read_file`
when it needs deeper domain knowledge.

---

## 1. Canonical P&L formula

All numbers are normalized to the `reporting_currency` (default `EUR`) using
ECB daily fixing rates (see `references/fx_and_currency.md`).

```
gross_revenue          = Σ shopify.orders.total_price
- refunds              = Σ shopify.refunds.amount
- discounts            = Σ shopify.orders.total_discounts        (already netted by Shopify if you use total_price — see schema.md note 1)
──────────────────────
= net_revenue

- cogs                 = Σ line_items.quantity × variant.cost
- shipping_cost        = Σ fulfillments.shipping_cost            (carrier-billed, NOT what customer paid)
- processing_fees      = Σ per-processor fee (Shopify Payments, Stripe, PayPal, Airwallex, …)
- ad_spend             = Σ Meta + Google + TikTok spend (incl. taxes where applicable)
- app_fees             = Σ Shopify app subscription + usage charges
- platform_fees        = Σ Shopify plan fee + transaction fee on non-Shopify-Payments orders
──────────────────────
= net_profit

contribution_margin   = (net_revenue - cogs - shipping_cost - processing_fees) / net_revenue
nc_roas               = net_revenue / ad_spend
mer                   = gross_revenue / ad_spend
poas                  = net_profit / ad_spend           # profit-on-ad-spend
```

The same formula lives in code at `scripts/pnl_builder.py::build_pnl`. **That
function is the single source of truth.** If the formula above and the code
disagree, the code wins and this doc must be updated.

---

## 2. Entry point

```python
from SKILLS.profit_tracker.scripts.orchestrator import compute_profit

result = await compute_profit(
    store_id="obliai-demo",
    period="last_30d",                # or {"start":"2026-03-01","end":"2026-03-31"}
    reporting_currency="EUR",
    include=["meta", "google", "tiktok", "shopify_apps"],
)
```

The return value is a `ProfitReport` pydantic model (see
`references/schema.md`). It contains the P&L breakdown, the per-channel ad
spend, the per-processor fee breakdown, a daily time-series, and a
`data_quality` block flagging any estimated / fallback values.

---

## 3. Routing — when the parent agent should call me

The parent agent should route to this skill when the user asks any of:

| Intent                                              | Example phrasing                                   |
|-----------------------------------------------------|----------------------------------------------------|
| Net profit / margin                                 | "quanto ho guadagnato ieri", "margin last week"    |
| POAS / MER / nc-ROAS                                | "what's my POAS this month"                        |
| Processing-fee breakdown                            | "how much Stripe is eating"                        |
| Ad spend vs. revenue reconciliation                 | "is Meta actually profitable"                      |
| Shopify subscription + app bill                     | "how much am I paying Shopify + apps"              |
| COGS / shipping cost drilldown                      | "what's my real cost per order"                    |
| Period comparisons                                  | "last 7d vs previous 7d"                           |

It should **not** route here for pure ad-platform tasks (creative ideation,
campaign launching, saturation detection) — those have dedicated skills.

---

## 4. Progressive disclosure of references

To keep the parent agent's context small, the reference files are **only**
loaded on demand:

| When the agent needs to …                     | Load                                  |
|-----------------------------------------------|----------------------------------------|
| Understand the output schema                  | `references/schema.md`                |
| Debug a Shopify query / scope problem         | `references/shopify.md`               |
| Validate a processor fee number               | `references/payment_processors.md`    |
| Explain a weird Meta number                   | `references/meta_ads.md`              |
| Explain a weird Google Ads number             | `references/google_ads.md`            |
| Explain a weird TikTok Ads number             | `references/tiktok_ads.md`            |
| Debug an FX conversion                        | `references/fx_and_currency.md`       |

The orchestrator never loads these — they are for humans and for the parent
LLM when it needs to reason about an anomaly.

---

## 5. Non-goals

- **Not** a forecasting tool. It reports past reality only.
- **Not** a bookkeeping system. It does not produce VAT-ready invoices.
- **Not** a Shopify app. It reads via Admin API; nothing is written back.
- **Not** a cache layer. Callers are responsible for caching `ProfitReport`
  objects if they want to (Redis key convention is documented in
  `INTEGRATION.md`).
