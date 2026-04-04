# Skill A -- Prompt Parser

## Description

Interprets free-text user prompts into structured search parameters using
Anthropic Claude Haiku. Extracts sources, countries, result count, signal type,
categories, gender, price range, and localized keywords per country.

## Endpoint

```
POST /prompt-parser/run
```

### Authentication

Pass a Bearer token in the `Authorization` header.

```
Authorization: Bearer <user_id>
```

## Input

| Field                | Type      | Required | Default | Description                                    |
|----------------------|-----------|----------|---------|------------------------------------------------|
| `prompt`             | `str`     | Yes      | --      | Free-text search prompt to parse.              |
| `override_countries` | `str[]?`  | No       | `null`  | Override the countries parsed from the prompt.  |

## Output

| Field          | Type           | Description                                |
|----------------|----------------|--------------------------------------------|
| `parsed`       | `ParsedParams` | Structured parameters extracted from prompt.|
| `raw_response` | `str`          | Raw Claude response text.                  |
| `used_defaults`| `bool`         | Whether fallback defaults were applied.    |

### ParsedParams

| Field                | Type                   | Description                              |
|----------------------|------------------------|------------------------------------------|
| `sources`            | `str[]`                | Data sources to query.                   |
| `countries`          | `str[]`                | ISO country codes.                       |
| `n_results`          | `int`                  | Number of results requested.             |
| `search_signal`      | `str`                  | Signal type (winner, trending, etc.).    |
| `categories`         | `str[]`                | Product categories.                      |
| `gender`             | `str?`                 | Target gender filter.                    |
| `price_max`          | `float?`               | Maximum price filter.                    |
| `price_min`          | `float?`               | Minimum price filter.                    |
| `keywords_by_country`| `dict[str, str[]]`     | Localized keywords per country.          |

## Caching

Results are cached in Redis for **30 minutes** (1800 s). The cache key is
`parser:{sha256(prompt)}`.

## curl Example

```bash
curl -X POST http://localhost:8000/prompt-parser/run \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer user_abc123" \
  -d '{
    "prompt": "Find trending women dresses in Europe under 50 euros",
    "override_countries": ["DE", "FR"]
  }'
```
