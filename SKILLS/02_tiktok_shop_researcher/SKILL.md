# Skill 02 -- TikTok Shop Researcher

## Purpose

Discover trending TikTok Shop products using the ScrapeCreators search API.
Given a list of countries and optional keywords, the skill fetches products,
normalises pricing (centesimi fix), applies progressive revenue-based filters
(T1-T5), and returns a curated shortlist.

## API

| Method | Path  | Auth   | Body                | Response                          |
|--------|-------|--------|---------------------|-----------------------------------|
| POST   | /run  | Bearer | `TikTokShopInput`   | `SkillResult[TikTokShopOutput]`   |

### Input schema

| Field                | Type                       | Default |
|----------------------|----------------------------|---------|
| countries            | list[str]                  | required|
| keywords_by_country  | dict[str, list[str]]       | {}      |
| n_results            | int                        | 10      |
| fetch_limit          | int or None                | None    |

### Output schema

| Field              | Type                      |
|--------------------|---------------------------|
| total_fetched      | int                       |
| total_after_filter | int                       |
| products           | list[TikTokShopProduct]   |
| countries_searched | list[str]                 |
| countries_skipped  | list[str]                 |
| filter_tier_used   | int                       |

## External dependency

* **ScrapeCreators** `GET /v1/tiktok/shop/search` -- requires `SCRAPECREATORS_API_KEY`.

## Caching

Redis key: `tiktok-shop:{sha256(params)}`, TTL 2 hours.

## Filter tiers

| Tier | Revenue range       | Freshness (days) | Fallback      |
|------|---------------------|-------------------|---------------|
| T1   | 89k -- 120k         | <= 30             |               |
| T2   | 50k -- 150k         | <= 45             |               |
| T3   | 20k -- 200k         | <= 60             |               |
| T4   | price 1-150, sold>=500 | --             |               |
| T5   | everything          | --                | always passes |

First tier with >= 3 results is used.

## Notes

* IE is silently skipped (not supported by ScrapeCreators).
* API calls are batched in groups of 5 with 200 ms delay between batches.
* Products are deduplicated by `item_id` before filtering.
