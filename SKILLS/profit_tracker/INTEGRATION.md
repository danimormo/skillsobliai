# Integrating `profit-tracker` into the parent agent

This document is for the engineer who is wiring the skill into the **mother
agent** (the top-level Claude agent that decides which sub-skill to call). If
you just want to know *what* the skill does, read `SKILL.md` instead.

---

## 1. Mounting

The skill follows the Anthropic Agent Skill convention
(`SKILL.md` + `scripts/` + `references/`) so you can point the parent agent's
skill loader at the folder:

```python
# in your parent agent bootstrap
from SKILLS.profit_tracker.scripts.orchestrator import compute_profit

AGENT_SKILLS = {
    # … other skills …
    "profit-tracker": compute_profit,
}
```

If you expose skills over HTTP (FastAPI pattern used elsewhere in this repo,
see `SKILLS/18_roas_monitor/router.py`) you can add a thin router that wraps
`compute_profit` — the skill itself is transport-agnostic.

---

## 2. Required environment variables

Copy these to `.env` (or your secret store). `.env.example` in the repo root
should list them.

```
# Shopify
SHOPIFY_SHOP_DOMAIN=obliai-demo.myshopify.com
SHOPIFY_ADMIN_TOKEN=shpat_xxx             # Admin API access token, scopes below
SHOPIFY_API_VERSION=2026-01

# Meta
META_ACCESS_TOKEN=EAAG...
META_AD_ACCOUNT_ID=act_1234567890

# Google Ads
GOOGLE_ADS_DEVELOPER_TOKEN=xxx
GOOGLE_ADS_CLIENT_ID=xxx.apps.googleusercontent.com
GOOGLE_ADS_CLIENT_SECRET=xxx
GOOGLE_ADS_REFRESH_TOKEN=xxx
GOOGLE_ADS_LOGIN_CUSTOMER_ID=1234567890   # MCC, digits only
GOOGLE_ADS_CUSTOMER_ID=9876543210         # target account, digits only

# TikTok Ads
TIKTOK_ACCESS_TOKEN=xxx
TIKTOK_ADVERTISER_ID=7100000000000000000

# FX (optional — falls back to ECB public endpoint if missing)
EXCHANGERATE_HOST_KEY=                    # optional, only if you hit rate limits

# Storage (optional — the skill can run stateless)
REDIS_URL=redis://localhost:6379/0        # used for FX cache and report cache
```

### Shopify scopes

The Admin API token needs, at minimum:

```
read_orders, read_all_orders,
read_products, read_inventory,
read_shipping,
read_fulfillments,
read_shopify_payments_payouts, read_shopify_payments_disputes,
read_shopify_payments_bank_accounts
```

For apps that don't have the `read_all_orders` scope Shopify caps history at
60 days — see `references/shopify.md`.

---

## 3. How the parent agent decides to call me

Add a tool definition that mirrors the intents listed in
`SKILL.md` §3. Recommended schema (Claude tool-use format):

```json
{
  "name": "profit_tracker.compute_profit",
  "description": "Compute the net P&L of a Shopify store for a period. Use when the user asks about profit, margin, POAS, MER, processing fees, app fees or overall store economics.",
  "input_schema": {
    "type": "object",
    "properties": {
      "store_id":            {"type": "string"},
      "period":              {"type": "string", "description": "last_7d | last_30d | last_90d | mtd | ytd | {start,end}"},
      "reporting_currency":  {"type": "string", "default": "EUR"},
      "include":             {"type": "array",  "items": {"type": "string"}, "default": ["meta","google","tiktok","shopify_apps"]},
      "compare_previous":    {"type": "boolean", "default": false}
    },
    "required": ["store_id", "period"]
  }
}
```

The orchestrator validates the `period` string through
`scripts/normalize.py::resolve_period`, so the parent agent can pass raw
natural-language presets like `last_30d` and not worry about date math.

---

## 4. Cost & latency budget

- Typical run for a store doing ~500 orders/day over 30 days:
  - Shopify: ~6 GraphQL page requests (≈3 s)
  - Meta: 1 insights call (≈1 s)
  - Google: 1 GAQL call (≈1 s)
  - TikTok: 1 insights call (≈1 s)
  - FX: 0 network calls on cache hit
  - **Total: ~5–7 s**
- The skill is I/O-bound; all clients are `httpx.AsyncClient`-based and run
  concurrently inside `compute_profit`.
- Memory: O(n_orders) while building the P&L, then discarded. A 30-day
  window with 15 k orders peaks around 40 MB.

### Caching

If `REDIS_URL` is set, the orchestrator caches `ProfitReport` objects under:

```
profit_tracker:{store_id}:{period_hash}:{currency}
```

Default TTL: 15 minutes. Pass `force_refresh=True` to bypass. Caching is
optional — the skill works fully stateless.

---

## 5. Error contract

All domain errors inherit from the repo's `core.errors.SkillBaseError`
hierarchy (see `core/errors.py`). The important ones:

| Exception                  | When it fires                                   | Suggested parent-agent behavior             |
|----------------------------|-------------------------------------------------|---------------------------------------------|
| `InvalidParamsError`       | bad period string, missing store_id             | surface to user, do not retry               |
| `InvalidApiKeyError`       | Shopify/Meta/Google/TikTok token rejected       | ask user to reconnect that integration      |
| `UpstreamError`            | any 5xx from an external API after retries      | show partial report, flag channel as stale  |

The report's `data_quality` block lists any channel that was skipped,
estimated, or FX-fallback-rated so the parent agent can add a natural-
language caveat.

---

## 6. Extending

Add a new ad channel in 3 steps:

1. Drop a `scripts/<channel>_ads_client.py` that exposes
   `async def fetch_spend(period, currency) -> list[DailyChannelSpend]`.
2. Register it in `orchestrator.AD_CHANNELS`.
3. Add a row to `references/schema.md` and a short reference doc.

The P&L builder (`scripts/pnl_builder.py`) is channel-agnostic — it only
cares about the aggregate `ad_spend` number.
