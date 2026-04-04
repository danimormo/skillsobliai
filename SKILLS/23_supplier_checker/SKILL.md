# Skill 23 -- Supplier Checker

## Description

Checks supplier viability for a dropshipping product by finding the best
supplier cost (via AliExpress search or AI estimation) and calculating the
exact net margin after all costs (supplier, shipping, ads, Shopify fees,
refund buffer).

## Endpoint

```
POST /supplier-checker/run
```

### Authentication

Pass a Bearer token in the `Authorization` header.

```
Authorization: Bearer <user_id>
```

## Input

| Field                  | Type     | Required | Default | Description                              |
|------------------------|----------|----------|---------|------------------------------------------|
| `product_title`        | `str`    | Yes      | --      | Product name to check.                   |
| `sale_price`           | `float`  | Yes      | --      | Planned retail price in USD.             |
| `supplier_cost`        | `float`  | No       | `null`  | Known supplier cost (skips lookup).      |
| `shipping_cost`        | `float`  | No       | `4.0`   | Estimated shipping cost per order.       |
| `daily_budget_usd`     | `float`  | No       | `30.0`  | Daily ad budget in USD.                  |
| `daily_orders_estimate`| `float`  | No       | `2.0`   | Expected daily orders.                   |
| `target_countries`     | `str[]`  | No       | `["IT"]`| Target market countries.                 |

## Margin Formula

```
cost_per_order_ads = daily_budget / max(daily_orders, 0.1)
shopify_fee = sale_price * 0.029 + 0.30
refund_buffer = sale_price * 0.03
total_cost = supplier + shipping + ads_per_order + shopify_fee + refund_buffer
net_margin_pct = (sale_price - total_cost) / sale_price
```

## Output

| Field                  | Type     | Description                                   |
|------------------------|----------|-----------------------------------------------|
| `product_title`        | `str`    | Echo of input product title.                  |
| `sale_price`           | `float`  | Echo of input sale price.                     |
| `best_supplier_cost`   | `float`  | Lowest supplier cost found.                   |
| `best_supplier_source` | `str`    | Source: "aliexpress", "ai_estimate", etc.     |
| `net_margin_pct`       | `float`  | Net margin as a decimal (e.g. 0.35 = 35%).   |
| `net_margin_usd`       | `float`  | Net margin in USD per order.                  |
| `is_viable`            | `bool`   | True if net_margin_pct > 0.15.                |
| `flag`                 | `str`    | "green" (>30%), "yellow" (>15%), "red".       |
| `breakdown`            | `dict`   | Cost breakdown by category.                   |
| `recommendation`       | `str`    | Human-readable recommendation.                |
| `alternative_suppliers`| `dict[]` | List of alternative supplier options.         |

## Caching

Results are cached in Redis for **12 hours** (43200 s).

## curl Example

```bash
curl -X POST http://localhost:8000/supplier-checker/run \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer user_abc123" \
  -d '{
    "product_title": "LED posture corrector",
    "sale_price": 39.99,
    "shipping_cost": 4.0,
    "daily_budget_usd": 30.0,
    "daily_orders_estimate": 3.0
  }'
```
