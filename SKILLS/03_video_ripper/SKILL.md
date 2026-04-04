# Skill 03 -- Video Ripper

## Purpose

Download winning TikTok Shop advertisement videos for a given product and store them in Supabase Storage for later creative analysis and remix workflows. Supports two data sources for maximum coverage.

## How It Works

1. **Fetch shop videos** -- Always calls the ScrapeCreators `/v1/tiktok/shop/videos` endpoint, sorted by engagement rate, for the specified `product_id`. Works for all regions.
2. **Enrich with product details** -- If `region == "US"` and a `product_url` is provided, also calls `/v1/tiktok/product?url={url}&get_related_videos=true&region=US`. This endpoint returns 500 for EU products, so errors are swallowed gracefully (empty list returned).
3. **Deduplicate** -- Merges results from both sources and removes duplicate videos by ID.
4. **Filter** -- Removes videos that fall below the caller's `min_views` and `min_engagement_rate` thresholds.
5. **Limit** -- Caps results at `max_videos`.
6. **Download & upload** -- Streams each qualifying video via httpx and uploads the MP4 to the `ripped-videos` Supabase Storage bucket under `{user_id}/{product_id}/{ad_id}.mp4`.
7. **Signed URLs** -- Generates a 24-hour signed URL for each uploaded file so downstream skills/UI can access the video without permanent public exposure.
8. **Timestamp hints** -- Calculates `hook_end_seconds` (first 15% of duration, capped at 3s) and `cta_start_seconds` (last 5s of video, floored at 0) for creative editing guidance.
9. **Persist** -- Saves full metadata to the `research_results` Supabase table with `skill = 'video-ripper'`.

## API

### `POST /video-ripper/run`

**Authentication**: Bearer token via `Authorization` header.

#### Request body

| Field                | Type         | Default  | Description                              |
|----------------------|--------------|----------|------------------------------------------|
| `product_id`         | string       | required | TikTok Shop product identifier           |
| `product_url`        | string\|null | null     | Full TikTok product URL (enables US enrichment) |
| `region`             | string       | "US"     | Product region code                      |
| `max_videos`         | int          | 5        | Maximum videos to download               |
| `min_views`          | int          | 10000    | Minimum view count filter                |
| `min_engagement_rate`| float        | 0.02     | Minimum engagement rate filter           |

#### Response (200)

```json
{
  "success": true,
  "data": {
    "product_id": "123456",
    "videos_downloaded": 3,
    "videos": [
      {
        "ad_id": "abc",
        "storage_path": "user-1/123456/abc.mp4",
        "signed_url": "https://...signedUrl...",
        "duration_seconds": 28.4,
        "views": 150000,
        "engagement_rate": 0.045,
        "hook_end_seconds": 3.0,
        "cta_start_seconds": 23.4,
        "thumbnail_url": "https://...",
        "source": "shop_videos"
      }
    ],
    "used_product_details_enrichment": false
  },
  "error": null,
  "cached": false,
  "execution_ms": 4820,
  "executed_at": "2026-04-04T12:00:00+00:00"
}
```

#### Error codes

| HTTP | Code             | Meaning                                |
|------|------------------|----------------------------------------|
| 401  | INVALID_API_KEY  | ScrapeCreators API key is invalid      |
| 422  | INVALID_PARAMS   | Bad request parameters                 |
| 429  | RATE_LIMIT       | Upstream rate limit exceeded           |
| 502  | UPSTREAM_ERROR   | ScrapeCreators unavailable after retry |

## Data Sources

| Endpoint | Regions | Notes |
|----------|---------|-------|
| `GET /v1/tiktok/shop/videos?product_id={id}&sort_by=engagement_rate` | All | Primary source, always called |
| `GET /v1/tiktok/product?url={url}&get_related_videos=true&region=US` | US only | Returns 500 on EU products; errors are gracefully handled |

## Caching

No cache is used. This skill performs write operations (downloading and uploading video files) so caching the result would be inappropriate. Passthrough `cache.py` functions are provided for interface consistency.

## Configuration

Requires the following environment variables (via `core.config.Settings`):

- `SCRAPECREATORS_API_KEY`
- `SCRAPECREATORS_BASE_URL` (default `https://api.scrapecreators.com`)
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`

The Supabase project must have a Storage bucket named `ripped-videos`.

## File Structure

```
SKILLS/03_video_ripper/
  __init__.py
  schemas.py          # Pydantic models
  api_client.py       # ScrapeCreators HTTP client (two endpoints)
  cache.py            # No-op passthrough (write-only skill)
  service.py          # VideoRipperSkill (BaseSkill impl)
  router.py           # FastAPI router
  SKILL.md            # This file
  tests/
    __init__.py
    test_service.py   # 3 tests: happy path, US enrichment, EU no enrichment
    test_router.py    # 2 tests: success, missing auth
```
