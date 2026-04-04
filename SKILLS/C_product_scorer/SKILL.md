# Skill C -- Product Scorer

## Description

Pure computation skill that scores products 0-100 based on multiple signals:
classification confidence, source-specific metrics (TikTok Shop sales/ratings,
Meta Ads longevity), EU market fit, gender match, and creator video virality.

## Endpoint

```
POST /product-scorer/run
```

### Authentication

```
Authorization: Bearer <user_id>
```

## Input

| Field       | Type     | Required | Default | Description                            |
|-------------|----------|----------|---------|----------------------------------------|
| `items`     | `dict[]` | Yes      | --      | Product items with classification data.|
| `params`    | `dict`   | Yes      | --      | Search params (gender, etc.).          |
| `n_results` | `int`    | No       | `10`    | Max products to return.                |

## Scoring Formula

| Component          | Max Points | Description                                |
|--------------------|------------|--------------------------------------------|
| Confidence         | 40         | `confidence * 40`                          |
| Source signal       | 35         | TikTok: sold/rating/trust. Meta: days running. |
| EU market fit      | 5          | Bonus if `eu_market_fit` is true.          |
| Gender match       | 10         | Bonus if item gender matches params gender.|
| Creator virality   | 15         | Based on creator video play count.         |
| **Total**          | **100**    |                                            |

## Filters

1. **Gender filter (HARD)**: If params.gender is "woman", exclude items with gender "man" and vice versa.
2. **Fashion filter**: Only items with `is_fashion=True` AND `confidence >= 0.7`.
3. Results sorted by score descending, top `n_results` returned.

## Output

| Field                  | Type              | Description                        |
|------------------------|-------------------|------------------------------------|
| `total_input`          | `int`             | Total items received.              |
| `total_after_filter`   | `int`             | Items after gender + fashion filter.|
| `total_returned`       | `int`             | Items in final response.           |
| `products`             | `ScoredProduct[]` | Scored and ranked products.        |
| `gender_filter_applied`| `bool`            | Whether gender filter removed items.|

## Caching

No caching -- pure computation.

## curl Example

```bash
curl -X POST http://localhost:8000/product-scorer/run \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer user_abc123" \
  -d '{
    "items": [
      {
        "item_id": "p1", "title": "Summer Dress", "image_url": "https://example.com/dress.jpg",
        "product_url": "https://shop.com/dress", "price": 29.99, "currency": "EUR",
        "country": "DE", "source": "tiktok_shop", "is_fashion": true, "confidence": 0.95,
        "category": "dresses", "gender": "woman", "eu_market_fit": true,
        "sold_count": 50000, "rating": 4.8, "trust_label": "best_seller"
      }
    ],
    "params": {"gender": "woman"},
    "n_results": 5
  }'
```
