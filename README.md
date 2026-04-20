# Supplier Finder

Image-first reverse lookup of dropshipping products across **9 marketplaces**:
AliExpress, Alibaba, 1688, Temu, Shein, Taobao, DHgate, CJDropshipping, Spocket.

Ingest a competitor product URL *or* a raw photo → get back a ranked list of
supplier candidates with confidence score, price, thumbnail and estimated
shipping time. **Zero paid APIs** — the whole stack runs on open-source tools
(Playwright, Tesseract.js, CLIP via `@xenova/transformers`, Cheerio).

## Quick start

```bash
cd supplier-finder
npm install
npm run playwright:install          # one-time: downloads Chromium
cp .env.example .env

# (Optional) Redis for 24h caching
docker run --rm -d -p 6379:6379 redis:7-alpine
echo "REDIS_URL=redis://localhost:6379" >> .env

npm run dev                         # Express on :8787 with hot reload
```

### Docker Compose (one-shot)

```bash
docker compose up --build
# Supplier-finder on http://localhost:8787, Redis on :6379
```

## REST API

### `POST /api/suppliers/find`

Body accepts either JSON or `multipart/form-data`.

**JSON (URL-based)**
```bash
curl -X POST http://localhost:8787/api/suppliers/find \
  -H 'content-type: application/json' \
  -d '{
    "url": "https://brand.com/products/cat-fountain",
    "suppliers": ["AliExpress", "Shein", "Temu"]
  }'
```

**JSON (base64 image)**
```bash
IMG_B64=$(base64 -i product.jpg)
curl -X POST http://localhost:8787/api/suppliers/find \
  -H 'content-type: application/json' \
  -d "{\"imageBase64\":\"$IMG_B64\"}"
```

**Multipart (file upload, ≤10MB)**
```bash
curl -X POST http://localhost:8787/api/suppliers/find \
  -F "image=@./product.jpg" \
  -F "suppliers=AliExpress,Shein" \
  -F "noCache=true"
```

**Response shape**
```json
{
  "query": {
    "inputType": "url",
    "originalSource": "https://brand.com/products/cat-fountain",
    "extractedTitle": "Ultra Silent Cat Fountain 2.5L",
    "extractedKeywords": ["fountain", "cat", "silent", "pet"],
    "timestamp": "2026-04-20T12:34:56.789Z",
    "requestId": "b1d2e3f4-…",
    "warnings": []
  },
  "results": [
    {
      "supplier": "AliExpress",
      "status": "FOUND",
      "confidence": 87,
      "productUrl": "https://www.aliexpress.com/item/10050012345.html",
      "title": "Pet Cat Water Fountain 2.5L Ultra Quiet Automatic",
      "price": { "value": 12.99, "currency": "USD" },
      "thumbnail": "https://ae01.alicdn.com/kf/S1234.jpg",
      "estimatedShippingDays": 15
    },
    { "supplier": "Shein", "status": "NOT_AVAILABLE", "reason": "confidence 38 < 50" },
    { "supplier": "Taobao", "status": "ERROR", "error": "captcha wall detected", "reason": "captcha" }
  ],
  "executionTimeMs": 8432,
  "cacheHit": false
}
```

### `GET /health`

```bash
curl http://localhost:8787/health
# {"status":"ok","service":"supplier-finder","version":"0.1.0"}
```

## CLI

```bash
npm run find -- --url="https://brand.com/products/foo" --pretty
npm run find -- --image=./product.jpg --suppliers=AliExpress,Shein,1688
npm run find -- --url="https://brand.com/x" --no-cache | jq '.results[] | select(.status=="FOUND")'
```

## Programmatic use (library)

```ts
import { findSuppliers, shutdownPipeline } from '@oblivion/supplier-finder';

const result = await findSuppliers({
  url: 'https://brand.com/products/foo',
  suppliers: ['AliExpress', '1688'],
});

console.log(result.results.filter((r) => r.status === 'FOUND'));
await shutdownPipeline();
```

## Architecture

```
src/
├── index.ts               orchestrator (cache → normalize → visual → suppliers)
├── server.ts              Express REST endpoint
├── cli.ts                 commander-based CLI
├── shutdown.ts            graceful teardown
├── config.ts              env parsing
├── types.ts               FinderInput/Result, SupplierResponse, SearchInput
├── input/
│   ├── urlExtractor.ts    Playwright + Cheerio page scrape
│   └── imageHandler.ts    Sharp preprocessing (resize/normalize/strip-EXIF)
├── ocr/tesseractEngine.ts Tesseract.js worker + keyword builder
├── matching/
│   ├── clipSimilarity.ts  CLIP ViT-B/32 via @xenova/transformers
│   └── textSimilarity.ts  Levenshtein + Jaccard + keyword hit rate
├── visualSearch/
│   ├── googleLens.ts      primary engine (uploadbyurl OR file upload)
│   ├── yandexImages.ts    backup (Asian marketplace specialist)
│   ├── bingVisual.ts      backup
│   ├── candidates.ts      normalizeAnchors (pure) + extractAnchors (DOM)
│   ├── domains.ts         matchSupplier suffix matcher
│   └── index.ts           runVisualSearch aggregator
├── suppliers/
│   ├── base.ts            abstract BaseSupplier + classifyError
│   ├── pdp.ts             shared fetchPdp / pickFirstSearchHref / validateListing
│   ├── registry.ts        SupplierName → crawler map
│   ├── aliexpress.ts      (template)
│   ├── alibaba.ts  alibaba1688.ts  temu.ts  shein.ts  taobao.ts
│   └── dhgate.ts  cjdropshipping.ts  spocket.ts
└── utils/
    ├── logger.ts          Pino (pretty in dev, JSON in prod)
    ├── browser.ts         playwright-extra + stealth, humanDelay, detectCaptcha
    ├── userAgents.ts      20-entry desktop UA pool
    ├── rateLimiter.ts     Bottleneck per-domain (3 concurrent, 1s interval)
    └── cache.ts           Redis read-through/write-through + buildCacheKey
```

## Pipeline flow

1. **Cache check** — deterministic key = `sha256(url | image bytes) + sorted(suppliers)`.
2. **Input normalization** — URL → Playwright scrape → og/LD-JSON/heuristic extraction → Sharp preprocess; raw image → Sharp preprocess directly.
3. **OCR + CLIP** (parallel) — Tesseract.js for text, CLIP ViT-B/32 for a 512-dim visual embedding.
4. **Reverse image search** (parallel) — Google Lens primary, Yandex + Bing as fallback. Candidates bucketed per supplier.
5. **Per-supplier crawl** (parallel, `Promise.allSettled`) — each supplier reuses Step-4 candidates first, falls back to keyword search.
6. **Validation** — hybrid score: 70% CLIP cosine + 30% title similarity. Below `MIN_CONFIDENCE` → `NOT_AVAILABLE`.
7. **Cache write + response** — TTL 24h default.

## Environment variables

| Variable                     | Default                      | Description                                               |
|------------------------------|------------------------------|-----------------------------------------------------------|
| `NODE_ENV`                   | `development`                | Switches Pino transport (pretty ↔ JSON)                   |
| `LOG_LEVEL`                  | `info`                       | Pino level                                                |
| `PORT`                       | `8787`                       | Express listen port                                       |
| `REDIS_URL`                  | *(unset)*                    | `redis://…` — absent ⇒ cache is a no-op                   |
| `CACHE_TTL_SECONDS`          | `86400`                      | 24 h                                                      |
| `MIN_CONFIDENCE`             | `50`                         | Below this → `NOT_AVAILABLE`                              |
| `AMBIGUOUS_CONFIDENCE`       | `70`                         | Reserved for center-crop rescue                           |
| `HEADLESS`                   | `true`                       | Playwright headless mode                                  |
| `BROWSER_TIMEOUT_MS`         | `30000`                      | Per-navigation                                            |
| `ACTION_DELAY_MIN_MS`        | `500`                        | `humanDelay` lower bound                                  |
| `ACTION_DELAY_MAX_MS`        | `2000`                       | `humanDelay` upper bound                                  |
| `PROXY_URL`                  | *(unset)*                    | `http://user:pass@host:port` (residential recommended for 1688/Taobao) |
| `MAX_CONCURRENT_PER_DOMAIN`  | `3`                          | Bottleneck                                                |
| `MIN_INTERVAL_MS`            | `1000`                       | Bottleneck minTime                                        |
| `PIPELINE_TIMEOUT_MS`        | `15000`                      | Reserved for future hard ceiling                          |
| `SUPPLIER_TIMEOUT_MS`        | `12000`                      | Per-supplier Bottleneck expiration                        |
| `OCR_LANGS`                  | `eng`                        | Add `+chi_sim` for Chinese labels (~20MB, +200ms cold)    |

## Testing

```bash
npm test                           # ~100 unit tests, no network
npm run test:coverage              # with coverage report (v8)
RUN_CLIP_E2E=1 npm test clipEmbed  # opt-in: downloads CLIP weights
```

## Troubleshooting

### Temu / Shein return `ERROR / captcha`
Those sites fingerprint aggressively. The stealth plugin bypasses the default
challenge, but repeated requests from the same IP trigger a slider CAPTCHA we
don't attempt to solve (by design — see "Legality" below). Workarounds:

1. Set `PROXY_URL` to a residential proxy. Chinese IPs are best for 1688 and
   Taobao; US/EU for Shein and Temu.
2. Lower `MAX_CONCURRENT_PER_DOMAIN` to `1` and raise `MIN_INTERVAL_MS` to
   `3000` for a "slow crawl" profile.
3. Accept the `NOT_AVAILABLE` / `ERROR` response — the rest of the pipeline
   is designed never to stall on a single supplier.

### 1688 / Taobao always return `ERROR / blocked`
Both sites geo-fence aggressively outside mainland China. Setting a Chinese
residential proxy is the only reliable fix. For Taobao, also note that most
search endpoints require login; the image-search path (Step-4 candidate) has
a much higher success rate than the keyword path.

### CLIP download fails on cold start
`@xenova/transformers` lazy-loads ~50MB of weights from HuggingFace on first
call. If you're offline at startup the first image request logs
`clip embedding unavailable` and the pipeline falls back to text-only
matching (score capped at 60). To pre-warm:

```bash
node -e "import('@xenova/transformers').then(m=>m.pipeline('image-feature-extraction','Xenova/clip-vit-base-patch32'))"
```

### "OCR produced no text" warning
Expected for product photos without labels (solid-color items, raw fabric,
etc.). Not an error — the pipeline falls back to visual-only search.

## Edge cases handled

| Scenario                                         | Behavior                                                            |
|--------------------------------------------------|---------------------------------------------------------------------|
| CAPTCHA on a supplier page                       | `ERROR` with `reason: 'captcha'`, no retry, others continue         |
| Visually ambiguous product (generic t-shirt etc) | Text-only score capped at 60; below `MIN_CONFIDENCE` → `NOT_AVAILABLE` |
| Image with watermark                             | `centerCrop()` helper available (opt-in); strips outer 30% borders  |
| Source URL redirect / 404 / 5xx                  | `PipelineError` on 404; graceful warning on partial hydration       |
| Multi-variant products (colors/sizes)            | CLIP picks the variant whose thumbnail ranks highest                |
| Cloudflare / Temu fingerprint walls              | `ERROR` documented; proxy + slow-crawl profile recommended          |
| Low-resolution image (<300×300)                  | Warning in response, pipeline still runs                            |
| OCR yields no text                               | Warning, visual-only search                                         |

## Roadmap

- **Native supplier image search**: AliExpress and Taobao expose `imageSearch`
  endpoints on their mobile API. Stable integration requires a cookie+token
  handshake we haven't built yet. ROI is moderate because Google Lens covers
  ~90% of the value.
- **Additional suppliers** (Modalyst, Syncee, SaleHoo) — scaffolded as
  `null` entries in the registry for now.
- **Per-supplier confidence weights** — tune the 70/30 CLIP/text split per
  marketplace (Shein is text-heavy, 1688 is visual-heavy).
- **Center-crop rescue** — automatically re-score borderline matches (60-70)
  after running `centerCrop()` to discount watermarks.
- **Persisted embeddings** — cache the CLIP embedding of every visited PDP
  keyed on URL so repeat queries are O(1).

## Legality

The pipeline scrapes public pages; CAPTCHAs and anti-bot walls are respected
(we never try to solve them). When a site becomes definitively inaccessible
the module returns `NOT_AVAILABLE` / `ERROR` and the pipeline continues — it
is **not** designed to force access. Commercial use should still comply with
each marketplace's Terms of Service; residential proxies are the user's
responsibility.

## License

Proprietary — © Oblivion SaaS.
