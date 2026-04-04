# Skill 09 -- PDP Builder

## Description

Generates product detail page (PDP) copy via OpenRouter / DeepSeek. Returns
structured sections including headlines, benefit bullets, FAQ, urgency text, and
a CTA, optimised for the requested copy angle and language.

## Endpoint

```
POST /pdp-builder/run
```

### Authentication

Pass a Bearer token in the `Authorization` header.

```
Authorization: Bearer <user_id>
```

## Input

| Field                | Type     | Required | Default    | Description                            |
|----------------------|----------|----------|------------|----------------------------------------|
| `product_title`      | `str`    | Yes      | --         | Name of the product.                   |
| `product_description`| `str?`   | No       | `null`     | Optional longer description.           |
| `price`              | `float`  | Yes      | --         | Current selling price.                 |
| `original_price`     | `float?` | No       | `null`     | Crossed-out / compare-at price.        |
| `category`           | `str?`   | No       | `null`     | Product category.                      |
| `copy_angle`         | `str`    | No       | `"benefit"`| Copywriting angle.                     |
| `target_audience`    | `str?`   | No       | `null`     | Audience description.                  |
| `language`           | `str`    | No       | `"en"`     | ISO language code.                     |

## Output

| Field        | Type          | Description                            |
|--------------|---------------|----------------------------------------|
| `pdp_id`     | `str`         | Unique identifier for this generation. |
| `sections`   | `PDPSections` | Structured PDP copy sections.          |
| `copy_angle` | `str`         | Echo of the requested angle.           |
| `language`   | `str`         | Echo of the requested language.        |
| `word_count` | `int`         | Total word count across all sections.  |

### PDPSections

| Field              | Type       | Description                          |
|--------------------|------------|--------------------------------------|
| `headlines`        | `str[]`    | Multiple headline options.           |
| `subheadline`      | `str`      | Supporting subheadline.              |
| `benefit_bullets`  | `str[]`    | Key benefit bullet points.           |
| `description_long` | `str`      | Full product description.            |
| `faq`              | `dict[]`   | FAQ items with question and answer.  |
| `urgency_text`     | `str`      | Urgency / scarcity copy.            |
| `cta_text`         | `str`      | Call-to-action text.                |

## Caching

Results are cached in Redis for **4 hours** (14 400 s). The cache key is scoped
per user and per unique combination of input parameters.
