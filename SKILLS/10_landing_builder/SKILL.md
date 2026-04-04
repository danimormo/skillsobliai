# Skill 10 -- Landing Builder

## Description

Generates landing page copy via OpenRouter / DeepSeek. Returns a list of
structured sections (hero, benefits, testimonials, FAQ, CTA) ready to be
rendered by a front-end template.

## Endpoint

```
POST /landing-builder/run
```

### Authentication

Pass a Bearer token in the `Authorization` header.

```
Authorization: Bearer <user_id>
```

## Input

| Field                 | Type     | Required | Default | Description                          |
|-----------------------|----------|----------|---------|--------------------------------------|
| `product_title`       | `str`    | Yes      | --      | Name of the product.                 |
| `product_description` | `str`    | Yes      | --      | Product description.                 |
| `price`               | `float`  | Yes      | --      | Current selling price.               |
| `original_price`      | `float?` | No       | `null`  | Compare-at price.                    |
| `target_audience`     | `str`    | Yes      | --      | Audience description.                |
| `main_benefit`        | `str`    | Yes      | --      | Primary product benefit.             |
| `cta_destination_url` | `str`    | Yes      | --      | URL the CTA links to.               |
| `language`            | `str`    | No       | `"en"`  | ISO language code.                   |

## Output

| Field              | Type              | Description                        |
|--------------------|-------------------|------------------------------------|
| `landing_id`       | `str`             | Unique identifier for generation.  |
| `sections`         | `LandingSection[]`| Ordered list of page sections.     |
| `total_word_count` | `int`             | Total words across all sections.   |
| `language`         | `str`             | Echo of the requested language.    |

### LandingSection

| Field      | Type   | Description                                     |
|------------|--------|-------------------------------------------------|
| `type`     | `str`  | Section type (hero, benefits, testimonials, etc).|
| `headline` | `str`  | Section headline.                                |
| `body`     | `str`  | Section body text.                               |
| `cta_text` | `str?` | CTA button text (null if not applicable).        |

## Caching

Results are cached in Redis for **4 hours** (14 400 s). The cache key is scoped
per user and per unique combination of input parameters.
