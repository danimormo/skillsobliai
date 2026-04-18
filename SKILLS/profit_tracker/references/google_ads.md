# Google Ads — implementation notes

Like Meta, we only need **spend**. Everything else is diagnostic.

---

## 1. Endpoint

Google Ads Query Language (GAQL) via the REST search endpoint:

```
POST https://googleads.googleapis.com/v17/customers/{CUSTOMER_ID}/googleAds:search
```

Headers:

```
Authorization: Bearer <access_token>             # from refresh-token flow
developer-token: <GOOGLE_ADS_DEVELOPER_TOKEN>
login-customer-id: <GOOGLE_ADS_LOGIN_CUSTOMER_ID># MCC, digits only
```

Version is pinned at `v17`; same reasoning as Meta.

---

## 2. The query

```sql
SELECT
  segments.date,
  metrics.cost_micros,
  metrics.impressions,
  metrics.clicks,
  metrics.conversions,
  metrics.conversions_value,
  customer.currency_code
FROM customer
WHERE segments.date BETWEEN '2026-03-01' AND '2026-03-31'
```

- `cost_micros` is in micros of the **account currency** — divide by
  1 000 000 before using.
- `segments.date` is in the account's timezone. Ad account timezone is
  set once at creation and can't be changed; we fetch it on client init
  via `SELECT customer.time_zone FROM customer LIMIT 1`.

---

## 3. OAuth

Google uses a 3-legged refresh-token flow. The skill never runs the
consent step itself — the parent app/agent bootstrap is expected to have
stored `GOOGLE_ADS_REFRESH_TOKEN`. `google_ads_client.py` only swaps
refresh → access tokens at runtime and caches access tokens for 50 min
(Google gives 60 min).

---

## 4. Currency

Same policy as Meta: convert from `customer.currency_code` to
`reporting_currency` with our ECB rate for `segments.date`. Google's own
currency conversion (`metrics.cost_per_conversion_currency`) is ignored.

---

## 5. Rate limits

- Per-developer-token: 15 000 ops/day (basic tier), 1 000 req/min.
- Per-account: 10 000 req/day.
- Unlikely to hit on a single profit report.

Errors handled:

- `PERMISSION_DENIED` → `InvalidApiKeyError` (usually wrong
  `login-customer-id`).
- `INVALID_ARGUMENT` on the GAQL → bubble up as `UpstreamError` with the
  GAQL in the message (don't leak the token).
- `UNAVAILABLE` / `DEADLINE_EXCEEDED` → retry 3× with backoff.

---

## 6. Multi-account (MCC) stores

If the merchant runs multiple CIDs under one MCC, the parent agent is
expected to pass `store_id → customer_id` mapping via environment /
config. This skill handles exactly one CID per run; the parent agent can
call it N times and sum.
