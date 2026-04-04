# Skill 3 -- Kalodata Ripper

## Purpose

Download top-performing TikTok Shop advertisement videos for a given product and store them in Supabase Storage for later creative analysis and remix workflows.

## How It Works

1. **Fetch videos** -- Calls the ScrapeCreators `/v1/tiktok/shop/videos` endpoint, sorted by engagement rate, for the specified `product_id`.
2. **Filter** -- Removes videos that fall below the caller's `min_views` and `min_engagement_rate` thresholds.
3. **Download & upload** -- Streams each qualifying video via httpx and uploads the MP4 to the `ripped-videos` Supabase Storage bucket under `{user_id}/{product_id}/{ad_id}.mp4`.
4. **Signed URLs** -- Generates a 24-hour signed URL for each uploaded file so downstream skills/UI can access the video without permanent public exposure.
5. **Timestamp hints** -- Calculates `suggested_hook_end` (first 15 % of duration, capped at 3 s) and `suggested_cta_start` (last 5 s of video) for creative editing guidance.
6. **Persist** -- Saves full metadata to the `research_results` Supabase table with `skill = 'kalodata-ripper'`.

## API

### `POST /kalodata-ripper/run`

#### Request body

| Field                | Type    | Default  | Description                          |
|----------------------|---------|----------|--------------------------------------|
| `product_id`         | string  | required | TikTok Shop product identifier       |
| `max_videos`         | int     | 5        | Maximum videos to download           |
| `min_views`          | int     | 10 000   | Minimum view count filter            |
| `min_engagement_rate`| float   | 0.02     | Minimum engagement rate filter       |

#### Query parameters

| Parameter  | Type   | Default     | Description |
|------------|--------|-------------|-------------|
| `user_id`  | string | "anonymous" | Caller identity for storage pathing and metadata |

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
        "storage_url": "https://...signedUrl...",
        "duration_seconds": 28.4,
        "views": 150000,
        "engagement_rate": 0.045,
        "suggested_hook_end": 3.0,
        "suggested_cta_start": 23.4,
        "thumbnail_url": "https://..."
      }
    ]
  },
  "error": null,
  "cached": false,
  "execution_ms": 4820,
  "executed_at": "2026-04-01T12:00:00+00:00"
}
```

#### Error codes

| HTTP | Code             | Meaning                                |
|------|------------------|----------------------------------------|
| 401  | INVALID_API_KEY  | ScrapeCreators API key is invalid      |
| 422  | INVALID_PARAMS   | Bad request parameters                 |
| 429  | RATE_LIMIT       | Upstream rate limit exceeded           |
| 502  | UPSTREAM_ERROR   | ScrapeCreators unavailable after retry |

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
SKILLS/kalodata_ripper/
  __init__.py
  schemas.py          # Pydantic models
  api_client.py       # ScrapeCreators HTTP client with retry
  cache.py            # No-op passthrough (write-only skill)
  service.py          # KalodataRipperSkill (BaseSkill impl)
  router.py           # FastAPI router
  SKILL.md            # This file
  tests/
    __init__.py
    test_service.py
    test_router.py
```
