# Skill 24 — Trend Analyzer

End-to-end product-research / trend-validation skill for dropshippers.
Accepts free text, a product URL, or an image and returns a structured
`TrendReport` with a 0–100 score, GO/WAIT/AVOID verdict, five sub-scores,
saturation / geography / price / seasonality / creative blocks, and a
Markdown rendering.

## Endpoint

```
POST /api/skills/trend-analyzer/run
Authorization: Bearer <user_id>
```

Errors: `422` invalid params, `402` cost cap exceeded (bypass with
`force=true`), `502` upstream auth / network failure.

## Input (`TrendAnalyzerInput`)

Exactly one of `text` / `url` / `image_url` / `image_b64` must be provided.

| Field            | Type            | Required | Default                          | Description |
|------------------|-----------------|----------|----------------------------------|-------------|
| `text`           | `str`           | –        | —                                | Free-text keyword. |
| `url`            | `HttpUrl`       | –        | —                                | Product page URL (Shopify, Amazon, TikTok Shop, …). |
| `image_url`      | `HttpUrl`       | –        | —                                | Public image URL (JPG/PNG/WEBP). |
| `image_b64`      | `str`           | –        | —                                | Base64-encoded image bytes. |
| `countries`      | `str[]`         | No       | `["US","GB","IT","FR","DE","ES"]` | ISO-3166-1 alpha-2 codes for geo analysis. |
| `skip_creatives` | `bool`          | No       | `false`                          | Skip LLM creative-angle generation. |
| `fast`           | `bool`          | No       | `false`                          | Reserved for tier-3 providers. |
| `no_cache`       | `bool`          | No       | `false`                          | Force-fetch, bypass Redis cache. |
| `force`          | `bool`          | No       | `false`                          | Bypass the cost hard-cap. |

## Output

`SkillResult[TrendAnalyzerOutput]` where `TrendAnalyzerOutput.report` is a
`TrendReport` and `TrendAnalyzerOutput.markdown` is a human-readable render.

Top-level report fields:

- `score` (0–100) + `verdict` (`GO` / `WAIT` / `AVOID`) + `rationale`
- `sub_scores[]` — momentum, saturation, ad velocity, seasonality, margin
  (each with `value`, `weight`, and human `explanation`)
- `interest_over_time[]` — 12-month Google Trends series
- `seasonality.peak_months` / `valley_months` / `summary`
- `saturation.stores_found` + `top_competitors[]` (up to 5)
- `meta_ads.active_ads_{7,30}d` + `top_advertisers` + `earliest_ad_date` + `media_distribution`
- `tiktok.hashtag_score` + `product_mentions` + `top_videos_views`
- `geography[]` — up to 5 countries with current interest + 30d-vs-90d delta
- `price.retail_price_{median,range}_usd`, `supplier_price_median_usd`,
  `gross_margin_pct`
- `creatives.angles[]` (up to 5) + `creatives.hooks[]` (up to 5)
- `cost.total_usd` + per-entry breakdown + `cap_hit` flag
- `warnings[]` — non-fatal upstream failures, stale caches, etc.

## Pipeline

```
input → normalize (Claude Haiku vision/text) → ProductFingerprint
     → parallel providers
           ├─ google_trends      (interest-over-time + geography + related queries)
           ├─ meta_ads           (Playwright scrape of public ad library)
           ├─ tiktok             (Creative Center public JSON)
           ├─ shopify_saturation (340-store /products.json fuzzy-match scan)
           ├─ aliexpress         (supplier median price, Playwright)
           └─ google_shopping    (retail median + range, Playwright)
     → seasonality detection on the 12m interest series
     → price-signal computation (retail vs supplier → margin %)
     → scoring (5 sub-scores → weighted aggregate → verdict)
     → LLM creative generation (5 angles + 5 hooks)
     → Markdown + JSON output, with cost breakdown + warnings
```

## Scoring algorithm

| Sub-score          | Weight | Rule |
|--------------------|--------|------|
| Momentum           | 30 %   | Δ% Google Trends last 30 d vs prior 90 d. ±50 % ↔ 0–100 pts. |
| Saturation (inv.)  | 25 %   | `100 − min(100, stores × 2)`. |
| Ad Velocity        | 20 %   | Fraction of 30-day Meta ads launched in the last 7 days, rescaled. |
| Seasonality Fit    | 15 %   | Distance from peak month: 0 mo = 100 pts, 6 mo = 0 pts. |
| Margin Potential   | 10 %   | Gross margin %: >60 % = 100 pts, <20 % = 0 pts, linear. |

**Verdict:**

- `GO` — score ≥ 70 **and** saturation sub-score ≥ 40
- `WAIT` — score 50–69, or score ≥ 70 with saturation < 40
- `AVOID` — score < 50

## Cost budget

- **Target per run:** < $0.02
- **Hard cap:** $0.05 (configurable via `TREND_ANALYZER_COST_CAP_USD`),
  raises `COST_CAP_EXCEEDED` → HTTP 402 unless `force=true`.
- Only LLM calls (Claude Haiku 4.5 — normalize + creatives) incur cost.
  Every other provider is $0 and logs a zero-USD entry for traceability.

## Cache TTLs (Redis)

| Provider                  | TTL   |
|---------------------------|-------|
| Google Trends             | 24 h  |
| Meta Ads Library          | 12 h  |
| TikTok Creative Center    | 6 h   |
| Shopify `/products.json`  | 24 h  |
| AliExpress prices         | 48 h  |
| Google Shopping           | 24 h  |
| Product fingerprint       | 24 h  |
| LLM creatives             | never |

On cache miss + upstream failure the provider returns its previous cache
value (if any) with `stale=True`, or an empty signal so the rest of the
pipeline can still produce a usable report.

## Anti-bot notes (Playwright providers)

- `providers/_browser.py` centralizes headless Chromium launches with
  `playwright-stealth`, random UA rotation, and persistent cookie jars
  under `/tmp/trend_analyzer/cookies/<namespace>.json`.
- Meta Ads scraper enforces a 30-second per-host rate limit in-process.
- All scrapers tolerate HTTP 403 / 429 / DOM drift by returning empty
  signals; failures are surfaced in `report.warnings` not exceptions.

## Local development

```bash
pip install -r requirements.txt
playwright install chromium           # once, for Meta/AliExpress/GoogleShopping
export ANTHROPIC_API_KEY=sk-ant-...
export REDIS_URL=redis://localhost:6379
uvicorn main:app --reload

# Run the skill tests offline (no Redis, no network)
pytest SKILLS/24_trend_analyzer/tests/ -v
```

The test suite mocks Anthropic, httpx, and Playwright, so it runs in ~2 s
with zero network I/O.
