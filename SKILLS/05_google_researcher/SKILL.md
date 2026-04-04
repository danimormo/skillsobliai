# Skill 5 -- Google Researcher

## Overview

The **Google Researcher** skill analyses Google Trends interest-over-time data and
Reddit community sentiment for one or more keywords. It returns a structured report
with trend direction, peak months, Reddit posts with sentiment labels, and an
aggregated demand score (0-100).

## Endpoints

| Method | Path                        | Description                        |
| ------ | --------------------------- | ---------------------------------- |
| POST   | `/google-researcher/run`    | Execute a research query           |

### POST /google-researcher/run

**Headers**

| Header          | Required | Description                |
| --------------- | -------- | -------------------------- |
| Authorization   | Yes      | `Bearer <user_id>`        |

**Request body** -- `GoogleResearchInput`

| Field              | Type         | Default | Description                                    |
| ------------------ | ------------ | ------- | ---------------------------------------------- |
| keywords           | list[str]    | --      | Keywords to research (first is primary)         |
| region             | str          | "US"    | ISO country code for trends region              |
| reddit_subreddits  | list[str]    | []      | Optional subreddits to scope Reddit search      |
| trends_days        | int          | 90      | Number of days of trend data to retrieve        |

**Response body** -- `SkillResult[GoogleResearchOutput]`

The `data` field contains:

| Field                      | Type                  | Description                                  |
| -------------------------- | --------------------- | -------------------------------------------- |
| keyword                    | str                   | The primary keyword analysed                 |
| trend_direction            | str                   | "rising", "stable", or "declining"           |
| trend_data                 | list[TrendDataPoint]  | Daily interest values (date + 0-100 value)   |
| peak_months                | list[str]             | YYYY-MM months with value >= 80              |
| reddit_posts               | list[RedditPost]      | Posts with sentiment and key phrases          |
| overall_sentiment          | str                   | Most common sentiment across posts            |
| estimated_monthly_searches | int or null           | Monthly search volume (if available)          |
| estimated_cpc_usd          | float or null         | Estimated CPC in USD (if available)           |
| demand_score               | int                   | 0-100 composite demand score                  |

## Data Flow

1. Validate input (keywords must not be empty).
2. Check Redis cache (`google:{user_id}:{md5(params)}`, TTL 6 hours).
3. Call `GET /v1/google/trends` for the primary keyword.
4. Call `GET /v1/reddit/search` for the primary keyword.
5. Compute trend direction by comparing first-30-day avg vs last-30-day avg.
6. Identify peak months (any data point with value >= 80).
7. Assign Reddit post sentiment: score > 10 = positive, < 0 = negative, else neutral.
8. Extract key phrases from post titles.
9. Calculate demand score: 60% trend avg + 40% Reddit engagement.
10. Process secondary keywords (saved to Supabase only, not returned in response).
11. Persist primary result to `research_results` table (skill = `google-researcher`).
12. Cache result in Redis and return.

## Upstream APIs

- **ScrapeCreators** `GET /v1/google/trends` -- Google Trends interest-over-time
- **ScrapeCreators** `GET /v1/reddit/search` -- Reddit post search

Both use `x-api-key` header authentication with exponential-backoff retry (3 attempts).

## Caching

- **Backend**: Redis (async)
- **TTL**: 21 600 seconds (6 hours)
- **Key format**: `google:{user_id}:{md5(sorted_json_params)}`

## Error Handling

| HTTP Status | Condition                        |
| ----------- | -------------------------------- |
| 401         | Missing or invalid Bearer token  |
| 422         | Empty keywords / invalid params  |
| 429         | Upstream rate limit exceeded     |
| 502         | Upstream API error or bad key    |

## Configuration

Requires the following environment variables (via `core.config.Settings`):

- `SCRAPECREATORS_API_KEY`
- `SCRAPECREATORS_BASE_URL`
- `REDIS_URL`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
