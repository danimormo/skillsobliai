# Skill 6 -- Content Researcher

## Description

Discovers trending organic content across TikTok and Pinterest via the
ScrapeCreators API. Classifies each piece of content by format type (UGC,
demo, review, lifestyle, transformation) and creative angle (problem/solution,
social proof, lifestyle, trend), extracts hook text, and computes aggregate
engagement insights.

## Endpoint

```
POST /content-researcher/run
```

### Authentication

Pass a Bearer token in the `Authorization` header. The token is used as the
user identifier for caching and result persistence.

```
Authorization: Bearer <user_id>
```

## Input

| Field                | Type       | Required | Default                  | Description                                       |
|----------------------|------------|----------|--------------------------|---------------------------------------------------|
| `keywords`           | `str[]`    | Yes      | --                       | Keywords to search for across platforms.           |
| `platforms`           | `str[]`    | No       | `["tiktok", "pinterest"]`| Platforms to search. Supported: tiktok, pinterest. |
| `region`             | `str`      | No       | `"US"`                   | ISO region code for the search.                    |
| `limit_per_platform` | `int`      | No       | `30`                     | Max items returned per platform per keyword.       |

## Output

| Field                | Type             | Description                                           |
|----------------------|------------------|-------------------------------------------------------|
| `total_items`        | `int`            | Number of unique content items returned.              |
| `items`              | `ContentItem[]`  | List of classified content items.                     |
| `top_formats`        | `str[]`          | Most frequent format types (up to 3).                 |
| `top_angles`         | `str[]`          | Most frequent creative angles (up to 3).              |
| `avg_engagement_rate`| `float`          | Average engagement rate across all items.             |
| `content_insights`   | `str`            | Human-readable summary of patterns and insights.      |

### ContentItem object

| Field            | Type     | Description                                                     |
|------------------|----------|-----------------------------------------------------------------|
| `platform`       | `str`    | Source platform (`tiktok` or `pinterest`).                      |
| `content_id`     | `str`    | Unique content identifier on the platform.                      |
| `url`            | `str`    | Direct URL to the content.                                      |
| `thumbnail_url`  | `str?`   | Thumbnail image URL.                                            |
| `caption`        | `str?`   | Caption or description text.                                    |
| `likes`          | `int`    | Like count.                                                     |
| `views`          | `int?`   | View count (TikTok only).                                       |
| `saves`          | `int?`   | Save / repin count.                                             |
| `engagement_rate`| `float`  | Calculated engagement rate.                                     |
| `format_type`    | `str`    | `ugc`, `demo`, `review`, `lifestyle`, or `transformation`.     |
| `creative_angle` | `str`    | `problem_solution`, `social_proof`, `lifestyle`, or `trend`.   |
| `hook_text`      | `str?`   | First line of the caption (hook).                               |

### Engagement rate calculation

- **TikTok**: `likes / views`
- **Pinterest**: `saves / (saves + likes + 1)`

### Format type classification

Based on caption/description keywords:
- Contains "review" -> `review`
- Contains "transform" or "before"+"after" -> `transformation`
- Contains "demo", "how to", "tutorial" -> `demo`
- Contains "try", "unbox", "honest" -> `ugc`
- Contains "lifestyle", "routine", "day in", "aesthetic" -> `lifestyle`
- Default: `ugc` (TikTok) or `lifestyle` (Pinterest)

### Creative angle classification

- Contains "problem", "solution", "before", "after", "struggle", "fix" -> `problem_solution`
- Contains "everyone", "viral", "million", "sold out", "best seller" -> `social_proof`
- Contains "trend", "trending", "new", "just dropped", "hack" -> `trend`
- Default: `lifestyle`

## curl Example

```bash
curl -X POST http://localhost:8000/content-researcher/run \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer user_abc123" \
  -d '{
    "keywords": ["protein powder", "gym motivation"],
    "platforms": ["tiktok", "pinterest"],
    "region": "US",
    "limit_per_platform": 20
  }'
```

## Rate Limits

The upstream ScrapeCreators API may return HTTP 429 when rate-limited. The
client automatically retries up to 3 times with exponential backoff (1 s, 2 s,
4 s). If the limit is still exceeded after retries, a `429` is returned.

## Caching

Results are cached in Redis for **4 hours** (14400 s). The cache key is scoped
per user and per unique combination of input parameters:

```
content:{user_id}:{md5(params)}
```

A cached response sets `cached: true` in the result envelope.

## Data persistence

Results are saved to the `research_results` Supabase table with
`skill = 'content-researcher'`.
