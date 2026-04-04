# Skill 22 -- Saturation Detector

## Description

Checks product saturation by scanning Shopify stores. Randomly samples stores
from a curated list and uses fuzzy matching (rapidfuzz) to detect whether a
given product is already being sold. Returns a saturation index (0.0-1.0) and
actionable recommendation.

## Endpoint

```
POST /saturation-detector/run
```

### Authentication

Pass a Bearer token in the `Authorization` header. The token is used as the
user identifier.

```
Authorization: Bearer <user_id>
```

## Input

| Field              | Type     | Required | Default | Description                                |
|--------------------|----------|----------|---------|--------------------------------------------|
| `product_title`    | `str`    | Yes      | --      | The product title to check saturation for. |
| `product_keywords` | `str[]`  | No       | `[]`    | Additional keywords for fuzzy matching.    |
| `sample_size`      | `int`    | No       | `100`   | Number of stores to sample (max 500).      |

## Output

| Field              | Type     | Description                                         |
|--------------------|----------|-----------------------------------------------------|
| `product_title`    | `str`    | Echo of the input product title.                    |
| `stores_found`     | `int`    | Number of stores carrying a matching product.       |
| `stores_sampled`   | `int`    | Total stores checked.                               |
| `saturation_index` | `float`  | Ratio of stores_found / stores_sampled (0.0-1.0).  |
| `saturation_level` | `str`    | "low", "medium", "high", or "very_high".            |
| `flag`             | `str`    | "green", "yellow", or "red".                        |
| `recommendation`   | `str`    | Human-readable recommendation.                      |
| `found_in_stores`  | `str[]`  | List of store domains where the product was found.  |

## Saturation Levels

| Index Range   | Level      | Flag   |
|---------------|------------|--------|
| < 0.05        | low        | green  |
| 0.05 - 0.15  | medium     | yellow |
| 0.15 - 0.30  | high       | red    |
| >= 0.30       | very_high  | red    |

## Caching

Results are cached in Redis for **6 hours** (21600 s). The cache key is based
on the MD5 hash of the product title: `saturation:{md5(title)}`.

## curl Example

```bash
curl -X POST http://localhost:8000/saturation-detector/run \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer user_abc123" \
  -d '{
    "product_title": "LED posture corrector",
    "product_keywords": ["posture belt", "back corrector"],
    "sample_size": 50
  }'
```
