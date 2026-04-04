# Skill 12 -- Creative Ideator

## Description

Generates creative briefs and ad angles via OpenRouter / DeepSeek. Returns
multiple creative angles with hooks, 30-second scripts, format suggestions,
visual references, target emotions, and estimated CTR tiers.

## Endpoint

```
POST /creative-ideator/run
```

### Authentication

Pass a Bearer token in the `Authorization` header.

```
Authorization: Bearer <user_id>
```

## Input

| Field                | Type     | Required | Default  | Description                              |
|----------------------|----------|----------|----------|------------------------------------------|
| `product_title`      | `str`    | Yes      | --       | Name of the product.                     |
| `product_description`| `str`    | Yes      | --       | Product description.                     |
| `category`           | `str?`   | No       | `null`   | Product category.                        |
| `target_audience`    | `str?`   | No       | `null`   | Audience description.                    |
| `price`              | `float?` | No       | `null`   | Product price.                           |
| `competitor_hooks`   | `str[]`  | No       | `[]`     | Competitor ad hooks for reference.        |
| `top_content_angles` | `str[]`  | No       | `[]`     | Top performing content angles.            |
| `num_angles`         | `int`    | No       | `3`      | Number of creative angles to generate.   |
| `platform`           | `str`    | No       | `"meta"` | Target ad platform.                      |
| `language`           | `str`    | No       | `"en"`   | ISO language code.                       |

## Output

| Field               | Type              | Description                              |
|---------------------|-------------------|------------------------------------------|
| `product_title`     | `str`             | Echo of the product title.               |
| `angles`            | `CreativeAngle[]` | List of generated creative angles.       |
| `recommended_angle` | `str`             | Name of the recommended best angle.      |
| `platform`          | `str`             | Echo of the target platform.             |

### CreativeAngle

| Field                | Type     | Description                              |
|----------------------|----------|------------------------------------------|
| `name`               | `str`    | Short name for the angle.                |
| `hook`               | `str`    | Opening hook text.                       |
| `script_30s`         | `str`    | Full 30-second ad script.               |
| `format`             | `str`    | Suggested format (UGC, static, etc).     |
| `visual_refs`        | `str[]`  | Visual reference suggestions.            |
| `target_emotion`     | `str`    | Emotion the ad should evoke.             |
| `estimated_ctr_tier` | `str`    | Estimated CTR tier (high/medium/low).    |

## Caching

Results are cached in Redis for **4 hours** (14 400 s). The cache key is scoped
per user and per unique combination of input parameters.
