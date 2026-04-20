# Troubleshooting

Common failure modes and how to react.

## Manual smoke tests (recommended baseline)

Run these before reporting the skill broken. They cover 90% of the real-world distribution:

| Scenario | Example URL | What to check |
|---|---|---|
| Shopify single product | `https://www.allbirds.com/products/mens-tree-runners` | `/products.json` 200, 1 product returned, ≥5 images, ≥1 variant |
| Shopify collection | `https://www.allbirds.com/collections/mens` | Paginated through 2+ pages, respects `max_products` |
| Shopify homepage | `https://www.allbirds.com/` | Kind=homepage, isShopify=true, `max_products` cap |
| WooCommerce product | any WP site with `/?post_type=product` | JSON-LD found OR WooCommerce selectors hit |
| Product with 3 options | any Shopify shirt with size+color+material | `optionNames.length === 3`, variants = size×color×material |
| Product with 10+ images | Shopify product with many images | `images_uploaded` in final result ≥ 10 |

Status as of last commit:
- Allbirds (Shopify) — tested OK
- Generic WooCommerce with JSON-LD — tested OK
- WooCommerce without JSON-LD and matrix variants — **not fully tested**, variants collapse to single "Default"
- Magento 2 — selectors present, real-world prices (EU format) verified with Cheerio extraction

## Failure: extraction returns no product / empty images

Symptoms: final result has `status: "error"` with `Extraction failed: no JSON-LD and no matching selectors`.

Likely causes:
1. Site requires login / geo-block.
2. Cloudflare Turnstile / Bot Fight Mode blocks Playwright.
3. Fully client-rendered SPA with no JSON-LD and no matching selectors.

Actions:
- Check `references/extraction-patterns.md` and consider adding a platform entry if the site is a recognizable template.
- If the site is critical, the mother agent can fall back to a manual form (user pastes title/price/images) — NOT handled here.

## Failure: images 403 / 401 / hotlink protection

Symptoms: `[clone] WARN image 403, retry with Referer: ...` and ultimately `Image upload failed, skipping`.

Actions:
- We already retry once with `Referer: {origin}` + browser UA.
- If still blocked, the source probably signs URLs or checks session cookies. The product still imports but with fewer (or zero) images.
- Workaround at the mother-agent level: re-fetch images through a proxy or Playwright `page.request.get()` within the same session as the page render.

## Failure: 429 / 430 Shopify throttling

Symptoms: repeated `[clone] WARN GraphQL throttled (429)`.

Actions:
- We honor `Retry-After` and pause when `throttleStatus.currentlyAvailable < 100`.
- If you see this on every call, the shop probably has a concurrent process hammering the API. Lower the `concurrency` on `ShopifyClient.gqlQueue` from `2` to `1`.

## Failure: productCreate userErrors: "Handle has already been taken"

Symptoms: `createProduct` throws even though dedup said no dupe.

Cause: the handle collides with a deleted product whose handle is still reserved, OR a race with another import.

Actions:
- Append a suffix (e.g. `-v2`) to the handle. This skill currently does NOT auto-retry with a new handle — it returns `status: error`. TODO: add collision fallback.

## Failure: variants mismatch ("Variant options do not match product options")

Cause: option names in variants don't match exactly those declared in `productOptions` (case-sensitive, trim-sensitive).

Actions:
- Inspect the extracted product and confirm `optionNames` contains every `selectedOptions[].name`.
- If JSON-LD used `color` lowercase but selectors produced `Color`, normalize to one casing.

## Failure: OpenRouter timeout / rate limit

Symptoms: `[clone] WARN OpenRouter retry 1: ...` repeated 3 times, then fallback to clone mode (copy-transformer.js returns `cloneMode` on parse failure).

Actions:
- Check `OPENROUTER_API_KEY` is set.
- Verify the account has credits.
- Fall back to `copy_mode: "clone"` to bypass AI entirely.

## Known limits (TODO)

- WooCommerce matrix variants (`form.variations_form data-product_variations` JSON attribute) not parsed.
- No `Retry-After` handling on OpenRouter 429 responses (we just exponential-backoff).
- No concurrency limit on multi-product collection imports — runs sequentially to avoid Shopify throttling. For very large catalogs (>500 products) consider a queue at the mother-agent level.
- `compare_at_price` uses a flat 1.3x multiplier when markup > 1. Not configurable per-product.
- Image deduplication (don't re-upload if Shopify already has bytes-equivalent media) not implemented.
