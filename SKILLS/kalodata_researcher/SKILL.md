# Skill 2 -- Kalodata Researcher

## Overview

The **Kalodata Researcher** skill discovers high-opportunity products on TikTok Shop by querying the ScrapeCreators API (Kalodata dataset). It searches by keyword, enriches each product with 30-day analytics (GMV, units sold, growth rate, shop count), calculates an **opportunity score**, and returns a ranked list of products.

## Opportunity Score

```
opportunity_score = (gmv_growth_pct * units_sold_30d) / shop_count
```

A high score indicates a product with strong sales momentum and low competition -- an attractive opportunity for sellers and affiliates.

## API Endpoints

### `POST /kalodata-researcher/run`

Run a research query.

**Headers**

| Header          | Required | Description               |
|-----------------|----------|---------------------------|
| Authorization   | Yes      | `Bearer <token>`          |

**Request body**

```json
{
  "keywords": ["dog toy", "pet"],
  "category": "Pets",
  "region": "US",
  "days_range": 30,
  "limit": 20
}
```

| Field       | Type       | Default | Constraints         |
|-------------|------------|---------|---------------------|
| keywords    | list[str]  | --      | 1-3 items, required |
| category    | str\|null  | null    | Optional filter      |
| region      | str        | "US"    | TikTok Shop region   |
| days_range  | int        | 30      | 1-365                |
| limit       | int        | 20      | 1-100                |

**Response (200)**

```json
{
  "success": true,
  "data": {
    "total_products": 15,
    "products": [
      {
        "product_id": "123456",
        "title": "Squeaky Dog Toy",
        "category": "Pets",
        "price_range": {"min": 4.99, "max": 9.99, "currency": "USD"},
        "gmv_30d": 125000.0,
        "gmv_growth_pct": 45.2,
        "units_sold_30d": 8500,
        "shop_count": 3,
        "top_shop": "PetParadise",
        "opportunity_score": 128066.67,
        "thumbnail_url": "https://..."
      }
    ],
    "region": "US",
    "days_range": 30
  },
  "cached": false,
  "execution_ms": 1234,
  "executed_at": "2026-04-01T12:00:00+00:00",
  "error": null
}
```

## Architecture

```
router.py  -->  service.py (KalodataResearcherSkill)
                    |
                    +-- cache.py   (Redis, 2h TTL)
                    +-- api_client.py  (ScrapeCreators HTTP)
                    +-- Supabase   (research_results table)
```

### Upstream API calls

1. `GET /v1/tiktok/shop/products` -- keyword search (one call per keyword, concurrent).
2. `GET /v1/tiktok/shop/analytics` -- per-product enrichment (concurrent, semaphore-capped at 10).

### Retry policy

Retries on HTTP 429 and 5xx with exponential backoff (1 s, 2 s, 4 s) for up to 3 attempts.

### Caching

Results are cached in Redis for **2 hours** (7200 s).
Key format: `kalodata:{user_id}:{md5(params_json)}`.

### Persistence

Every successful result is inserted into the `research_results` Supabase table with:
- `user_id`, `skill` ("kalodata-researcher"), `request_id`, `input_params`, `result`.

## Error codes

| Code             | HTTP | Cause                                |
|------------------|------|--------------------------------------|
| INVALID_API_KEY  | 502  | ScrapeCreators rejected the API key  |
| INVALID_PARAMS   | 422  | Upstream rejected query parameters   |
| UPSTREAM_ERROR   | 502  | ScrapeCreators 5xx or timeout        |
| RATE_LIMITED     | 429  | ScrapeCreators rate limit exhausted  |

## Running tests

```bash
pytest SKILLS/kalodata_researcher/tests/ -v
```
