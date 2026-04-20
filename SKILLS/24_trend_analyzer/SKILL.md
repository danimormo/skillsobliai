# Skill 24 — Trend Analyzer

End-to-end product-research / trend-validation skill for dropshippers.
Accepts free text, a product URL, or an image and returns a structured
`TrendReport` with a 0–100 score, GO/WAIT/AVOID verdict, sub-scores,
saturation / geography / price / creative-angles blocks.

## Status

- **Phase 1 (landed):** skeleton, schemas, cost tracker, Redis cache,
  router registration. Returns an empty `TrendReport` scaffold.
- **Phase 2 (next):** normalizers (text/url/image → fingerprint) and
  tier-1 providers (Google Trends, Meta Ads Library, TikTok Creative
  Center, Shopify `/products.json`, AliExpress, Google Shopping).
- **Phase 3:** scoring, seasonality detection, geography ranking, LLM
  creative generation, markdown + JSON reports.

## Endpoint

```
POST /api/skills/trend-analyzer/run
Authorization: Bearer <user_id>
```

## Input (`TrendAnalyzerInput`)

Exactly one of `text` / `url` / `image_url` / `image_b64` must be provided.

| Field            | Type            | Required | Default                          | Description |
|------------------|-----------------|----------|----------------------------------|-------------|
| `text`           | `str`           | –        | —                                | Free-text keyword. |
| `url`            | `HttpUrl`       | –        | —                                | Product page URL. |
| `image_url`      | `HttpUrl`       | –        | —                                | Public image URL. |
| `image_b64`      | `str`           | –        | —                                | Base64-encoded image. |
| `countries`      | `str[]`         | No       | `["US","GB","IT","FR","DE","ES"]` | ISO-3166-1 alpha-2 codes for geo analysis. |
| `skip_creatives` | `bool`          | No       | `false`                          | Skip LLM creative-angle generation. |
| `fast`           | `bool`          | No       | `false`                          | Skip tier-3 providers. |
| `no_cache`       | `bool`          | No       | `false`                          | Force-fetch, bypass Redis cache. |
| `force`          | `bool`          | No       | `false`                          | Bypass the cost hard-cap. |

## Output (`TrendAnalyzerOutput`)

See `schemas.py` for the authoritative shape. Top-level fields:

- `report.score` (0–100) + `report.verdict` (`GO` / `WAIT` / `AVOID`)
- `report.sub_scores` — momentum, saturation, ad velocity, seasonality, margin
- `report.interest_over_time` — 12-month Google Trends series
- `report.seasonality` — detected peaks / valleys
- `report.saturation` — Shopify store count + top-5 competitors
- `report.meta_ads` — active ads 7d/30d, top advertisers, media mix
- `report.tiktok` — hashtag score + top-video views
- `report.geography` — top-5 growing countries (delta 30d vs 90d)
- `report.price` — retail/supplier price + estimated margin %
- `report.creatives` — 5 angles + 5 hooks (skippable)
- `report.cost` — per-provider cost breakdown, cap-hit flag
- `markdown` — human-readable rendering of the full report

## Scoring algorithm

| Sub-score          | Weight | Rule |
|--------------------|--------|------|
| Momentum           | 30 %   | Δ% Google Trends last 30 d vs prior 90 d. ±50 % ↔ 0–100 pts. |
| Saturation (inv.)  | 25 %   | `100 − min(100, stores × 2)`. |
| Ad Velocity        | 20 %   | Meta ads last 7 d vs last 30 d. |
| Seasonality Fit    | 15 %   | Distance from peak in months. |
| Margin Potential   | 10 %   | Gross margin %: >60 % = 100 pt, <20 % = 0 pt. |

**Verdict:**

- `GO` — score ≥ 70 **and** saturation sub-score ≥ 40
- `WAIT` — score 50–69, or score ≥ 70 with saturation < 40
- `AVOID` — score < 50

## Cost budget

- **Target per run:** < $0.02
- **Hard cap:** $0.05 (raises `COST_CAP_EXCEEDED`, HTTP 402)
- Bypass with `force=true` only when you explicitly accept the higher bill.

## Cache TTLs

| Provider                  | TTL   |
|---------------------------|-------|
| Google Trends             | 24 h  |
| Meta Ads Library          | 12 h  |
| TikTok Creative Center    | 6 h   |
| Shopify `/products.json`  | 24 h  |
| AliExpress prices         | 48 h  |
| LLM creatives             | never |
