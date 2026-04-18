# Meta (Facebook + Instagram) Ads — implementation notes

We only need **spend**. Attribution/revenue from Meta is advisory: the P&L
always trusts Shopify for revenue.

---

## 1. Endpoint

```
GET /v19.0/act_{AD_ACCOUNT_ID}/insights
```

Version is pinned at `v19.0` in `meta_ads_client.py`; Meta deprecates versions
roughly every 24 months and the field names for `spend` / `purchase_roas`
have been stable since v7.

---

## 2. Required fields

```
fields = [
    "date_start",
    "spend",
    "account_currency",
    "impressions",
    "clicks",
    "actions",              # for purchases, optional
    "action_values",        # for attributed revenue, optional
    "purchase_roas"         # optional, diagnostic only
]
```

Break down by day with:

```
time_increment = 1
time_range     = {"since": "YYYY-MM-DD", "until": "YYYY-MM-DD"}
level          = "account"
```

This returns one row per calendar day in the **ad account's timezone**.

---

## 3. Currency

`spend` is returned in `account_currency`. We convert to
`reporting_currency` via `scripts/fx.py::convert` using the daily ECB rate
for `date_start`. No Meta-side currency conversion is ever trusted — Meta
bills in the account currency, converts for display, and the two numbers
drift by ~0.3 %.

---

## 4. Attribution windows

For diagnostic `purchase_roas` / `action_values` we pin the attribution
setting explicitly so the number doesn't silently change when Meta updates
their defaults:

```
action_attribution_windows = ["7d_click", "1d_view"]
```

This is Meta's current default (since iOS 14.5) but being explicit makes
the skill reproducible across ad-account settings.

---

## 5. Rate limits & errors

Meta's rate limit on the insights endpoint is *app-scoped* and is rarely
hit by a single user. The client handles:

- `HTTP 400` with `error.code == 17` → app-level throttling. Retry with
  exponential backoff (1 s, 2 s, 4 s, max 3 retries).
- `HTTP 400` with `error.code == 190` → token invalid / expired →
  `InvalidApiKeyError`.
- `HTTP 500`/`502`/`503` → transient → retry (same policy as above).
- After retries exhausted → `UpstreamError`, channel is skipped in the
  report and added to `DataQuality.skipped_channels`.

---

## 6. What we don't pull

- Per-campaign / per-adset / per-ad spend — the P&L only needs the
  account total. If the parent agent needs per-campaign ROAS it should
  call the dedicated `18_roas_monitor` skill.
- `actions` / `action_values` — we fetch them for the diagnostic
  `platform_attributed_revenue` in `DailyChannelSpend.revenue`, but
  they're never fed into `net_revenue`.
