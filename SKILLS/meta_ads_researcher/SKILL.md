# Skill 1 -- Meta Ads Researcher

## Description

Searches the Meta (Facebook) Ad Library via the ScrapeCreators API to discover
competitor advertisements. Returns deduplicated, enriched ad objects with
computed fields such as `days_running` and `is_active`.

## Endpoint

```
POST /meta-ads-researcher/run
```

### Authentication

Pass a Bearer token in the `Authorization` header. The token is used as the
user identifier for caching and result persistence.

```
Authorization: Bearer <user_id>
```

## Input

| Field            | Type       | Required | Default                          | Description                          |
|------------------|------------|----------|----------------------------------|--------------------------------------|
| `search_terms`   | `str[]`    | Yes      | --                               | Up to 5 keywords to search for.      |
| `countries`      | `str[]`    | No       | `["IT","FR","DE","ES","GB"]`     | ISO-3166-1 alpha-2 country codes.    |
| `active_only`    | `bool`     | No       | `true`                           | Return only currently active ads.    |
| `limit_per_term` | `int`      | No       | `50` (max 100)                   | Max ads returned per search term.    |

## Output

| Field          | Type       | Description                              |
|----------------|------------|------------------------------------------|
| `total_ads`    | `int`      | Number of unique ads returned.           |
| `ads`          | `MetaAd[]` | Deduplicated list of ad objects.         |
| `search_terms` | `str[]`    | Echo of the search terms used.           |
| `countries`    | `str[]`    | Echo of the countries queried.           |
| `next_cursor`  | `str?`     | Pagination cursor (reserved for future). |

### MetaAd object

| Field          | Type     | Description                                 |
|----------------|----------|---------------------------------------------|
| `ad_id`        | `str`    | Unique ad identifier.                       |
| `page_name`    | `str`    | Name of the Facebook page running the ad.   |
| `page_id`      | `str`    | Facebook page ID.                           |
| `body`         | `str?`   | Ad body / primary text.                     |
| `title`        | `str?`   | Ad headline.                                |
| `snapshot_url`  | `str`    | URL to the ad creative snapshot.            |
| `landing_url`  | `str?`   | Destination URL of the ad.                  |
| `platforms`    | `str[]`  | Platforms where the ad runs (e.g. facebook).|
| `start_date`   | `str`    | ISO date when the ad started.               |
| `end_date`     | `str?`   | ISO date when the ad ended (null if active).|
| `is_active`    | `bool`   | Whether the ad is currently active.         |
| `days_running` | `int`    | Number of days the ad has been running.     |
| `countries`    | `str[]`  | Countries where the ad is shown.            |

## curl Example

```bash
curl -X POST http://localhost:8000/meta-ads-researcher/run \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer user_abc123" \
  -d '{
    "search_terms": ["protein powder", "whey isolate"],
    "countries": ["IT", "DE"],
    "active_only": true,
    "limit_per_term": 25
  }'
```

## Rate Limits

The upstream ScrapeCreators API may return HTTP 429 when rate-limited. The
client automatically retries up to 3 times with exponential backoff (1 s, 2 s,
4 s). If the limit is still exceeded after retries, a `502` is returned.

## Caching

Results are cached in Redis for **2 hours** (7200 s). The cache key is scoped
per user and per unique combination of input parameters. A cached response sets
`cached: true` in the result envelope.
