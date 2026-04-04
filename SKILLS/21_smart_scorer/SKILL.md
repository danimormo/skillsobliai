# Skill 21 -- Smart Scorer

## Description

Multi-source product scoring engine that evaluates a product across five
dimensions: trend momentum, multi-platform presence, saturation inverse,
estimated margin, and engagement. Returns a 0-100 score, a letter tier
(S/A/B/C/D), and a recommendation.

## Endpoint

```
POST /smart-scorer/run
```

### Authentication

Pass a Bearer token in the `Authorization` header.

```
Authorization: Bearer <user_id>
```

## Input

| Field                  | Type    | Required | Default | Description                            |
|------------------------|---------|----------|---------|----------------------------------------|
| `product_title`        | `str`   | Yes      | --      | Product name to score.                 |
| `total_ads`            | `int`   | No       | `0`     | Total ads found across sources.        |
| `active_ads`           | `int`   | No       | `0`     | Currently active ads.                  |
| `found_on_meta`        | `bool`  | No       | `false` | Product found on Meta Ad Library.      |
| `found_on_tiktok`      | `bool`  | No       | `false` | Product found on TikTok.               |
| `found_on_pinterest`   | `bool`  | No       | `false` | Product found on Pinterest.            |
| `shopify_store_count`  | `int`   | No       | `0`     | Number of Shopify stores selling it.   |
| `avg_engagement_rate`  | `float?`| No       | `null`  | Average engagement rate (0.0-1.0).     |
| `estimated_margin_pct` | `float?`| No       | `null`  | Estimated margin percentage (0.0-1.0). |
| `gmv_growth_pct`       | `float?`| No       | `null`  | GMV growth percentage (reserved).      |

## Scoring Formula

| Dimension          | Max Points | Logic                                         |
|--------------------|------------|-----------------------------------------------|
| Trend Momentum     | 25         | `(active_ads / total_ads) * 25`               |
| Multi-Platform     | 20         | `min(platforms_found * 7, 20)`                |
| Saturation Inverse | 25         | <10 stores=25, <50=18, <200=10, <500=4, else 0|
| Margin             | 20         | >60%=20, >40%=12, >25%=6, else 0             |
| Engagement         | 10         | >5%=10, >2%=5, else 0                        |

**Total: 0-100** (capped at 100)

## Tiers

| Tier | Score Range | Meaning         |
|------|-------------|-----------------|
| S    | >= 80       | Strong buy      |
| A    | >= 65       | Good opportunity|
| B    | >= 45       | Moderate        |
| C    | >= 25       | Weak            |
| D    | < 25        | Not recommended |

## Output

| Field            | Type   | Description                            |
|------------------|--------|----------------------------------------|
| `product_title`  | `str`  | Echo of the input product title.       |
| `score`          | `int`  | Computed score (0-100).                |
| `tier`           | `str`  | Letter tier: S, A, B, C, or D.        |
| `breakdown`      | `dict` | Per-dimension point breakdown.         |
| `recommendation` | `str`  | Human-readable recommendation.         |

## curl Example

```bash
curl -X POST http://localhost:8000/smart-scorer/run \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer user_abc123" \
  -d '{
    "product_title": "LED Camping Lantern",
    "total_ads": 40,
    "active_ads": 30,
    "found_on_meta": true,
    "found_on_tiktok": true,
    "found_on_pinterest": false,
    "shopify_store_count": 15,
    "avg_engagement_rate": 0.06,
    "estimated_margin_pct": 0.55
  }'
```

## Caching

No caching -- scores are computed on-the-fly from provided input.
