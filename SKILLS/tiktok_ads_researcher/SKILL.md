# Skill 4 -- TikTok Ads Researcher

## Overview

The **TikTok Ads Researcher** skill queries the ScrapeCreators TikTok Ads API to discover and analyse TikTok advertisements matching given keywords, regions, and (optionally) an industry vertical. Results are deduplicated, persisted to Supabase, and cached in Redis for 2 hours.

## API Endpoint

```
POST /tiktok-ads-researcher/run
```

### Request Body

| Field        | Type         | Default        | Description                                   |
|-------------|-------------|----------------|-----------------------------------------------|
| `user_id`   | `string`    | **required**   | Authenticated user identifier                 |
| `keywords`  | `list[str]` | **required**   | Search keywords (at least one)                |
| `regions`   | `list[str]` | `["US", "GB"]` | ISO-3166 region codes to search               |
| `industry`  | `string`    | `null`         | Optional industry filter                      |
| `days_range`| `int`       | `30`           | Look-back window in days (1-365)              |
| `limit`     | `int`       | `50`           | Max ads per keyword+region combination (1-200)|

### Response

Returns `SkillResult[TikTokAdsResearchOutput]`:

```json
{
  "success": true,
  "data": {
    "total_ads": 42,
    "ads": [
      {
        "ad_id": "abc123",
        "advertiser_name": "Brand Co",
        "video_url": "https://...",
        "thumbnail_url": "https://...",
        "caption": "Shop now!",
        "cta_text": "Learn More",
        "likes": 12000,
        "comments": 340,
        "shares": 890,
        "engagement_rate": 4.52,
        "estimated_spend": "$5,000-$10,000",
        "region": "US",
        "industry": "ecommerce",
        "duration_seconds": 15.0,
        "is_active": true
      }
    ],
    "keywords": ["skincare"],
    "regions": ["US", "GB"]
  },
  "cached": false,
  "execution_ms": 1230,
  "executed_at": "2026-03-31T14:22:01.123456+00:00",
  "error": null
}
```

## Architecture

```
router.py          FastAPI endpoint
    |
service.py         TikTokAdsResearcherSkill (BaseSkill)
    |--- cache.py  Redis read/write (TTL 7200s)
    |--- api_client.py  ScrapeCreators HTTP client
    |--- supabase  Persist to research_results table
```

### Upstream API

`GET {SCRAPECREATORS_BASE_URL}/v1/tiktok/ads`

Query parameters: `keyword`, `region`, `industry`, `objective=conversions`, `period`, `order_by=engagement_rate`, `limit`.

Authentication via `x-api-key` header.

### Retry Policy

- **Max retries:** 3
- **Backoff:** 1 s, 2 s, 4 s
- **Retried status codes:** 429 (rate limit), 5xx (server error)
- **Retried exceptions:** `httpx.ConnectError`, `httpx.ReadTimeout`

### Error Mapping

| Upstream Status | Raised Exception      | HTTP Response |
|----------------|-----------------------|---------------|
| 401            | `InvalidApiKeyError`  | 401           |
| 422            | `InvalidParamsError`  | 422           |
| 429 / 5xx      | `UpstreamError`       | 502           |

### Caching

- **Backend:** Redis (async)
- **TTL:** 7200 seconds (2 hours)
- **Key pattern:** `tiktok-ads:{user_id}:{md5(params)}`

### Persistence

Results are inserted into the `research_results` Supabase table with `skill = 'tiktok-ads-researcher'`.

## Configuration

Required environment variables (via `core.config.Settings`):

| Variable                  | Description                       |
|--------------------------|-----------------------------------|
| `SCRAPECREATORS_API_KEY` | API key for ScrapeCreators        |
| `SCRAPECREATORS_BASE_URL`| Base URL (default provided)       |
| `REDIS_URL`              | Redis connection string           |
| `SUPABASE_URL`           | Supabase project URL              |
| `SUPABASE_SERVICE_KEY`   | Supabase service-role key         |

## Testing

```bash
pytest SKILLS/tiktok_ads_researcher/tests/ -v
```

Tests cover:

- **test_service.py** -- happy path, upstream error propagation, cache hit
- **test_router.py** -- successful run, validation error
