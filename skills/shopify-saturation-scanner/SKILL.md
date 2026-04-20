# Shopify Saturation Scanner

Feature V2 of the Obliai dropshipping SaaS — given a product URL or image,
detects how many Shopify stores are already selling the (same or very similar)
product worldwide, in which geographic markets, and where blue-ocean
opportunities remain.

Supersedes the older Python `SKILLS/22_saturation_detector` (v1) which only
did keyword-matching against a sampled store list.

## Input

Exactly one of the two input modes is required:

| Field           | Type            | Description                                             |
|-----------------|-----------------|---------------------------------------------------------|
| `url`           | `string`        | Product page URL (Shopify or any e-commerce PDP)        |
| `imageBuffer`   | `Buffer`        | Raw product image bytes (JPG/PNG, ≥256×256 recommended) |
| `imageUrl`      | `string`        | Public URL to the image (required for Google Lens path) |
| `userId`        | `string`        | For logging / billing                                   |
| `scanId`        | `string`        | Optional external id                                    |
| `forceFresh`    | `boolean`       | Bypass 24h Supabase cache                               |
| `telegramChatId`| `string`        | Notify this chat when the job completes                 |

## Output (JSON)

```json
{
  "scan_id": "scan_1718...",
  "product_fingerprint": {
    "title_normalized": "magnetic eyelashes",
    "image_hash": "phash:ff00c3...",
    "identified_by": "url|image|hybrid",
    "raw_title": "Magnetic Eyelashes with Eyeliner Kit",
    "keywords": ["magnetic", "eyelashes", "eyeliner"],
    "generic_product": false
  },
  "saturation_score": 78,
  "saturation_zone": "red",
  "score_components": { "total_stores": 88, "market_concentration": 73, "ads_active_ratio": 62, "age_factor": 74 },
  "total_shopify_stores": 742,
  "ads_active_stores": 412,
  "markets": [
    { "country": "US", "store_count": 412, "saturation_level": "red", "avg_price_usd": 39.90,
      "top_stores": [{ "domain": "xxx.com", "product_url": "https://xxx.com/products/slug",
                       "match_confidence": 0.88, "ads_active": true }] },
    { "country": "DE", "store_count": 8, "saturation_level": "green" }
  ],
  "potential_markets": ["DE", "IT", "FR", "NL", "SE"],
  "blue_ocean_details": [
    { "country": "DE", "store_count": 8, "saturation_level": "green",
      "opportunity_flag": "BLUE_OCEAN", "google_trends_interest": 72,
      "population_millions": 84 }
  ],
  "recommendation": "Mercato US/UK saturo. Opportunità reale in DACH ed Europa mediterranea.",
  "duration_ms": 112843,
  "early_stopped": false,
  "from_cache": false
}
```

## Pipeline

1. **Fingerprint** (`lib/fingerprint.js`)
   - URL mode: fetch PDP, parse `og:*`, JSON-LD Product, Shopify `/products/slug.json`.
   - Image mode: pHash (16-bit) via `sharp` + `image-hash`, Google Lens enrichment
     via SerpAPI (primary choice per user decision).
2. **Discovery** (`lib/discovery.js`)
   - SerpAPI Google SERP queries across EN/DE/FR/IT/ES/NL/PT for
     `site:*.myshopify.com`, `"Powered by Shopify"`, `inurl:/products/`.
   - Seeded dataset from `/data/shopify_sample_stores.json`.
   - Google CSE fallback when SerpAPI fails or budget exceeded.
3. **Validation** (`lib/shopify-validator.js`)
   - Header probe (`x-shopify-stage`, `x-shopid`, …) + `/products.json?limit=250`.
   - Title similarity (Levenshtein + token overlap); threshold raised to 0.90 for
     generic products (≤2 tokens).
   - pHash Hamming distance fallback for renamed/translated products.
4. **Geo-location** (`lib/geo-locator.js`)
   - `/cart.js` → currency (strong), `/meta.json` → country (strong),
     TLD (medium), `franc` on homepage (medium), shipping footer (weak).
   - Confidence 0-100, capped.
5. **Meta Ads cross-ref** (`lib/ads-library.js`)
   - ScrapeCreators API to flag `ads_active:true` stores and discount zombie listings.
6. **Scoring** (`lib/saturation-scorer.js`)
   - Weighted 0.40/0.25/0.20/0.15, zones Green <100 / Yellow 100-500 / Red >500.
7. **Opportunity finder** (`lib/opportunity-finder.js`)
   - Country allowlist: US/GB/DE/FR/IT/ES/AU/CA/NL/SE/CH/AT/BE/IE/DK/NO/FI/PT.
   - Filtered by Google Trends (via SerpAPI) ≥ threshold.

## Data persistence — network effect

Confirmed at kickoff: we persist results in Supabase cross-tenant.

- `saturation_scans_cache(fingerprint_key, result jsonb, expires_at)` — 24h TTL.
- `shopify_stores_cache(domain, is_shopify, primary_market, match_payload jsonb)` — 24h TTL.

Re-scanning the same product (by any user) returns the cached result
instantly → amortizes SerpAPI cost across the user base.

GDPR: no email/personal data of store owners is stored. Only public store
metadata (domain, country hint, product title, price).

## Streaming progress

The worker reports progress via BullMQ `updateProgress(ev)` every time a
significant event happens (candidate found, store confirmed, geo located).
Base44 polls `getJob(id).progress` and renders a live store counter +
heatmap as the scan proceeds. Target UX: first confirmed store visible
within 5-10 s; full scan typically 60-180 s.

## Costs

Per scan (hard-capped at `$0.15` via `THRESHOLDS.maxCostUsd`):

| Source                       | Typical calls | Cost   |
|------------------------------|---------------|--------|
| SerpAPI Google (discovery)   | 8-30          | $0.04-0.15 |
| SerpAPI Google Lens (image)  | 0-1           | $0.015 |
| SerpAPI Google Trends        | 4-8           | $0.02-0.04 |
| ScrapeCreators (Meta Ads)    | 50-200        | included in stack quota |
| Supabase / Redis             | —             | ~$0 |
| **Total p50 / p95**          |               | **$0.07 / $0.14** |

Cache hits: $0 (the network-effect tradeoff in action).

## Rate limits

- 10 req/s per target domain (per `THRESHOLDS.storeValidationConcurrency` +
  `axios` timeouts).
- SerpAPI concurrency 4 (polite given shared account).
- Respects robots.txt scope: we only hit `/products.json`, `/cart.js`,
  `/meta.json`, `/` (homepage), and `/products/<slug>.json` — all
  documented public Shopify endpoints.

## Edge cases handled

| Case                                | Behavior                                             |
|-------------------------------------|------------------------------------------------------|
| Non-Shopify URL                     | Falls back to image-hash-only fingerprint + discovery |
| Image < 256×256                     | Continues with `low_resolution:true` flag, caller warns |
| Generic title ("white t-shirt")     | Similarity threshold raised to 0.90                  |
| `/products.json` blocked (401/403/429) | Store marked `is_shopify:true` + `matched:false, reason:"products_json_blocked"` |
| Product with color/size variants    | Grouped (matched on parent product title)            |
| <3 stores in a market               | Omitted from saturation breakdown (insufficient data)|
| SerpAPI down                        | CSE fallback; if both down, returns cached or error  |
| Scan exceeds 3-min deadline         | `early_stopped:true`, partial result returned        |

## Logging

JSON-structured, Sentry-ready. Every log line carries `user_id` and `scan_id`:

```json
{ "ts": "2026-04-20T09:12:33Z", "level": "info", "scan_id": "scan_1..",
  "user_id": "u_42", "duration_ms": 114_210, "stores": 742, "zone": "red" }
```

## Integration

- **Base44 UI**: see `integrations/Base44Scanner.jsx` — React component with
  progress streaming and market heatmap.
- **Python monolith**: call from FastAPI via HTTP `POST /scan` (see
  `integrations/README.md`). Alternatively, publish the scan directly to
  the Redis-backed BullMQ queue from Python with `rq`-compatible payload.
- **Direct**:
  ```js
  import { runScan, enqueueScan } from "./skills/shopify-saturation-scanner/index.js";
  const result = await runScan({ url: "https://x.com/products/y", userId: "u1" });
  // or async:
  const { jobId } = await enqueueScan({ url, userId: "u1", telegramChatId: "123" });
  ```
