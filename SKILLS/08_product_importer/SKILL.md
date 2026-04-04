# Skill 8 -- Product Importer

## Overview

The **product-importer** skill automates importing products into a user's connected
Shopify store.  It handles pricing (cost + markup), variant creation, image uploads,
and idempotency (duplicate-title detection).

## Endpoint

| Method | Path                        | Tag              |
|--------|-----------------------------|------------------|
| POST   | `/product-importer/run`     | product-importer |

## Authentication

Pass a Bearer token in the `Authorization` header.  The token is resolved to a
`user_id` which is used to look up the Shopify integration credentials in
`user_integrations`.

## Request Body (`ProductImportInput`)

| Field                | Type             | Required | Default | Description                              |
|----------------------|------------------|----------|---------|------------------------------------------|
| `shop_domain`        | string           | yes      | --      | Shopify store domain, e.g. `my.myshopify.com` |
| `title`              | string           | yes      | --      | Product title                            |
| `description_html`   | string           | yes      | --      | Product description (HTML)               |
| `vendor`             | string \| null   | no       | null    | Product vendor                           |
| `product_type`       | string \| null   | no       | null    | Product type                             |
| `tags`               | list[string]     | no       | []      | Product tags                             |
| `image_urls`         | list[string]     | yes      | --      | URLs of images to upload                 |
| `cost_usd`           | float            | yes      | --      | Product cost in USD                      |
| `markup_multiplier`  | float            | no       | 3.0     | Selling price = cost_usd * multiplier    |
| `variants`           | list[Variant]    | no       | []      | Product variants (see below)             |
| `supplier_source`    | string \| null   | no       | null    | Origin supplier platform                 |
| `supplier_product_id`| string \| null   | no       | null    | Product ID at the supplier               |

### ProductVariant

| Field               | Type           | Required | Default |
|---------------------|----------------|----------|---------|
| `title`             | string         | yes      | --      |
| `sku`               | string \| null | no       | null    |
| `price`             | float \| null  | no       | null    |
| `inventory_quantity` | int           | no       | 100     |

## Response Body (`ProductImportOutput`)

| Field                  | Type   | Description                                |
|------------------------|--------|--------------------------------------------|
| `job_id`               | string | UUID of the import job record              |
| `shopify_product_id`   | string | Shopify product ID                         |
| `shopify_product_url`  | string | Admin URL for the product                  |
| `shopify_storefront_url` | string | Public storefront URL                    |
| `title`                | string | Product title                              |
| `price`                | float  | Computed selling price                     |
| `variants_count`       | int    | Number of variants created                 |
| `images_uploaded`      | int    | Number of images successfully uploaded     |
| `status`               | string | `"completed"` or `"partial"`               |

## Workflow

1. Look up Shopify credentials from `user_integrations` (provider=shopify).
2. Create an `import_jobs` record with status `pending`.
3. Compute price as `cost_usd * markup_multiplier`.
4. Check if a product with the same title already exists (idempotency).
5. Create or update the Shopify product via the Admin REST API.
6. Upload images one by one.
7. Update the `import_jobs` record to `completed` or `partial`.
8. On full failure the job is marked `failed` with the error message.

## Caching

None. This skill performs write operations so caching is intentionally disabled.

## Error Handling

| Error                          | HTTP | Code                        |
|--------------------------------|------|-----------------------------|
| Missing Shopify integration    | 400  | INTEGRATION_NOT_CONNECTED   |
| Invalid input parameters       | 422  | INVALID_PARAMS              |
| Shopify rate limit             | 429  | SHOPIFY_RATE_LIMIT          |
| Shopify / upstream failure     | 502  | SHOPIFY_ERROR               |

## Database Tables

- **user_integrations** -- read to obtain `access_token` for the shop.
- **import_jobs** -- created per import; tracks status (`pending` -> `completed` | `partial` | `failed`).

## Credits

Each successful import consumes **2 credits**.
