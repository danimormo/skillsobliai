# TikTok Ads — implementation notes

Same contract as Meta / Google: we need daily **spend** in the account
currency, we convert to `reporting_currency`, we ignore TikTok's own
attributed revenue.

---

## 1. Endpoint

```
GET https://business-api.tiktok.com/open_api/v1.3/report/integrated/get/
```

Headers:

```
Access-Token: <TIKTOK_ACCESS_TOKEN>
Content-Type: application/json
```

Version: `v1.3`. TikTok changes path versions more aggressively than Meta
(4 versions in 2 years), so verify the version before upgrading.

---

## 2. Parameters

```json
{
  "advertiser_id": "7100000000000000000",
  "report_type":   "BASIC",
  "data_level":    "AUCTION_ADVERTISER",
  "dimensions":    ["advertiser_id", "stat_time_day"],
  "metrics":       ["spend", "impressions", "clicks",
                    "complete_payment", "complete_payment_roas"],
  "start_date":    "2026-03-01",
  "end_date":      "2026-03-31",
  "page":          1,
  "page_size":     1000
}
```

- `data_level = AUCTION_ADVERTISER` aggregates across all campaigns; no
  per-campaign breakdown, which is what we want.
- `metrics.spend` is already in the advertiser's currency (no micros
  weirdness). Fetch currency once via
  `GET /advertiser/info/?advertiser_ids=["..."]`.

---

## 3. Pagination

The response contains `page_info.total_page`. With
`data_level=AUCTION_ADVERTISER` a full year fits in page 1 (≤366 rows),
so pagination is a safety net rather than a hot path.

---

## 4. Attribution

TikTok exposes `complete_payment_roas` but the attribution window is
*account-level* and set in the TikTok Ads Manager UI (click 1/7/28 d,
view 1/7 d). The skill reads the current setting via
`/advertiser/info/` and records it in
`DailyChannelSpend.attribution_note` so the parent agent can include a
caveat when the user asks "why is TikTok's ROAS different from Triple
Whale's?".

---

## 5. Errors

- `code == 40105` → token expired → `InvalidApiKeyError`.
- `code == 40100` → permission missing → `InvalidApiKeyError`.
- `code == 51021` → rate limited → exponential backoff (1, 2, 4 s).
- `code == 40001` → bad parameter → don't retry; bubble as
  `UpstreamError`.

All other 5xx → retry then skip.
