# Skill B -- Vision Classifier

## Description

Classifies product images using Anthropic Claude Haiku Vision. Processes images
in configurable batches (default 5) with a 200ms delay between batches to
respect rate limits. Returns fashion/non-fashion classification with detailed
attributes.

## Endpoint

```
POST /vision-classifier/run
```

### Authentication

```
Authorization: Bearer <user_id>
```

## Input

| Field        | Type          | Required | Default | Description                       |
|--------------|---------------|----------|---------|-----------------------------------|
| `items`      | `ImageItem[]` | Yes      | --      | List of images to classify.       |
| `batch_size` | `int`         | No       | `5`     | Images per batch.                 |

### ImageItem

| Field       | Type   | Required | Description                |
|-------------|--------|----------|----------------------------|
| `item_id`   | `str`  | Yes      | Unique item identifier.    |
| `image_url` | `str`  | Yes      | URL to the product image.  |
| `title`     | `str?` | No       | Optional product title.    |

## Output

| Field             | Type               | Description                          |
|-------------------|--------------------|--------------------------------------|
| `total_processed` | `int`              | Total images processed.              |
| `total_fashion`   | `int`              | Count of fashion items.              |
| `total_non_fashion`| `int`             | Count of non-fashion items.          |
| `total_errors`    | `int`              | Count of classification errors.      |
| `items`           | `ClassifiedItem[]` | Detailed classification per item.    |

### ClassifiedItem

| Field                | Type      | Description                                  |
|----------------------|-----------|----------------------------------------------|
| `item_id`            | `str`     | Item identifier.                             |
| `image_url`          | `str`     | Original image URL.                          |
| `is_fashion`         | `bool`    | Whether the item is fashion.                 |
| `confidence`         | `float`   | Classification confidence 0-1.               |
| `category`           | `str`     | Product category.                            |
| `subcategory`        | `str`     | Product subcategory.                         |
| `target_gender`      | `str`     | Target gender (women/men/unisex/unknown).    |
| `gender`             | `str`     | Gender (woman/man/unisex).                   |
| `price_tier`         | `str`     | Price tier estimate.                         |
| `style_tags`         | `str[]`   | Up to 5 style tags.                          |
| `reasoning`          | `str`     | Classification reasoning.                    |
| `eu_market_fit`      | `bool`    | Whether item fits EU market.                 |
| `classification_error`| `str?`   | Error message if classification failed.      |

## Caching

No caching -- each classification is unique.

## curl Example

```bash
curl -X POST http://localhost:8000/vision-classifier/run \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer user_abc123" \
  -d '{
    "items": [
      {"item_id": "p1", "image_url": "https://example.com/dress.jpg", "title": "Summer Dress"},
      {"item_id": "p2", "image_url": "https://example.com/bag.jpg"}
    ],
    "batch_size": 5
  }'
```
