# Skill 7 -- Supplier Researcher

## Description

Searches multiple dropshipping supplier platforms (AliExpress, CJDropshipping,
Spocket) in parallel to find and compare product sourcing options. Returns
normalized product listings with computed margin analysis and highlights the
best picks by price, margin, and shipping speed.

## Endpoint

```
POST /supplier-researcher/run
```

### Authentication

Pass a Bearer token in the `Authorization` header. The token is used as the
user identifier for caching and result persistence.

```
Authorization: Bearer <user_id>
```

## Input

| Field              | Type       | Required | Default                              | Description                                       |
|--------------------|------------|----------|--------------------------------------|---------------------------------------------------|
| `product_name`     | `str`      | Yes      | --                                   | Product name or keyword to search for.            |
| `target_price_usd` | `float?`  | No       | `null`                               | Target retail price; used to compute margin_at_3x.|
| `ship_to_country`  | `str`     | No       | `"US"`                               | ISO-3166-1 alpha-2 destination country code.      |
| `sources`          | `str[]`   | No       | `["aliexpress", "cj", "spocket"]`    | Which supplier platforms to query.                |
| `limit_per_source` | `int`     | No       | `10`                                 | Max products returned per source.                 |

## Output

| Field              | Type               | Description                                            |
|--------------------|--------------------|--------------------------------------------------------|
| `total_found`      | `int`              | Total number of products found across all sources.     |
| `products`         | `SupplierProduct[]`| Full list of normalized product results.               |
| `best_price`       | `SupplierProduct?` | Product with the lowest total cost (cost + shipping).  |
| `best_margin`      | `SupplierProduct?` | Product with the highest margin_at_3x (if target set). |
| `fastest_shipping` | `SupplierProduct?` | Product with the lowest shipping_days_min.             |

### SupplierProduct object

| Field              | Type      | Description                                              |
|--------------------|-----------|----------------------------------------------------------|
| `source`           | `str`     | Platform: `"aliexpress"`, `"cj"`, or `"spocket"`.       |
| `product_id`       | `str`     | Platform-specific product identifier.                    |
| `title`            | `str`     | Product title / name.                                    |
| `cost_usd`         | `float`   | Unit cost in USD.                                        |
| `shipping_cost_usd`| `float`   | Shipping cost in USD.                                    |
| `shipping_days_min`| `int`     | Minimum estimated shipping days.                         |
| `shipping_days_max`| `int`     | Maximum estimated shipping days.                         |
| `moq`              | `int`     | Minimum order quantity.                                  |
| `supplier_rating`  | `float?`  | Supplier rating (scale varies by source).                |
| `image_urls`       | `str[]`   | Product image URLs.                                      |
| `product_url`      | `str`     | Direct link to the product on the source platform.       |
| `margin_at_3x`     | `float?`  | Margin ratio: `(target_price - cost - shipping) / target_price`. |
| `in_stock`         | `bool`    | Whether the product is currently in stock.               |

## Margin Calculation

When `target_price_usd` is provided, the `margin_at_3x` field is computed as:

```
margin_at_3x = (target_price_usd - cost_usd - shipping_cost_usd) / target_price_usd
```

A value of `0.67` means 67% margin. Products where cost + shipping exceeds the
target price will have a negative margin.

## curl Example

```bash
curl -X POST http://localhost:8000/supplier-researcher/run \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer user_abc123" \
  -d '{
    "product_name": "wireless earbuds bluetooth",
    "target_price_usd": 29.99,
    "ship_to_country": "US",
    "sources": ["aliexpress", "cj", "spocket"],
    "limit_per_source": 10
  }'
```

## Rate Limits

Each upstream API may return HTTP 429 when rate-limited. The client
automatically retries up to 3 times with exponential backoff (1 s, 2 s, 4 s).
If a source is still unavailable after retries, it is skipped and remaining
sources are still returned.

## Caching

Results are cached in Redis for **12 hours** (43200 s). The cache key is scoped
per user and per unique combination of input parameters:

```
supplier:{user_id}:{md5(params)}
```

A cached response sets `cached: true` in the result envelope.

## Data Sources

| Source       | API                                                            | Auth              |
|--------------|----------------------------------------------------------------|-------------------|
| AliExpress   | ScrapeCreators `GET /v1/aliexpress/search`                     | `x-api-key` header|
| CJDropshipping| `GET https://developers.cjdropshipping.com/api2.0/v1/product/list` | `CJ-Access-Token` header |
| Spocket      | `GET https://api.spocket.co/v2/products`                       | Bearer token      |
