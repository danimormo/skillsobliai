# Extraction patterns by platform

How the skill extracts product data by platform. Read this if extraction fails or returns incomplete data for a given source.

## Detection priority

1. Shopify native: `GET {origin}/products.json?limit=1` → 200 JSON with `products` array.
2. JSON-LD: `<script type="application/ld+json">` with `@type: "Product"` or `"ProductGroup"`.
3. Platform selectors (WooCommerce, Magento, BigCommerce, Squarespace).
4. Generic heuristics (h1 + og:image).

## Shopify (native)

- Single product: `GET /products/<handle>.json` → `{ product: {...} }`
- Collection:     `GET /collections/<handle>/products.json?limit=250&page=N`
- All products:   `GET /products.json?limit=250&page=N`

Fields we map:
- `title`, `body_html`, `vendor`, `product_type`, `tags`
- `options[].name` → option names
- `variants[]` → `title, price, compare_at_price, sku, option1/2/3, grams, inventory_quantity`
- `images[]` → `src, alt, position`

**Caveat**: `/products.json` is public and unpaginated past page 9 on some newer Shopify configurations. If collection paging stops early but we have <250 items, that's Shopify capping the public feed; use the Admin API if available.

## JSON-LD (schema.org/Product)

Best signal for non-Shopify sites. Common shapes:

```json
{
  "@context": "https://schema.org/",
  "@type": "Product",
  "name": "Wireless Headphones",
  "description": "Noise-cancelling...",
  "image": ["https://.../1.jpg", "https://.../2.jpg"],
  "brand": { "@type": "Brand", "name": "Sony" },
  "sku": "WH-1000",
  "offers": {
    "@type": "Offer",
    "price": "299.99",
    "priceCurrency": "EUR"
  }
}
```

**ProductGroup with hasVariant**:
```json
{
  "@type": "ProductGroup",
  "name": "T-Shirt",
  "hasVariant": [
    { "@type": "Product", "name": "T-Shirt Black S", "color": "Black", "size": "S", "sku": "TS-BK-S", "offers": { "price": "29" } }
  ]
}
```

Known quirks:
- Some sites embed multiple JSON-LD blocks (BreadcrumbList, Organization, Product). We pick the richest Product node.
- Shopify custom themes sometimes ship an incomplete JSON-LD with only `name`+`image` — we then fall through to selectors.

## WooCommerce

Detection: `body.woocommerce` or `.woocommerce-product-gallery` present.

| Field | Selector |
|---|---|
| title | `h1.product_title, .product_title` |
| price | `.price .woocommerce-Price-amount.amount` |
| images | `.woocommerce-product-gallery__image img, .woocommerce-product-gallery__image a` |
| description | `#tab-description, .woocommerce-Tabs-panel--description, .woocommerce-product-details__short-description` |

Variants: WooCommerce exposes variants via `form.variations_form data-product_variations` (JSON attribute). **Not yet parsed** by this extractor — TODO.

## Magento 2

Detection: `.product-info-main, .catalog-product-view`.

| Field | Selector |
|---|---|
| title | `.product-info-main .page-title .base` |
| price | `[data-price-type="finalPrice"] .price` |
| images | `.fotorama__stage__frame img, .gallery-placeholder img` |
| description | `.product.attribute.description .value, #description` |

Quirks: prices can be `€29,90` (EU format). Cheerio regex extracts first numeric group and normalizes `,` → `.`.

## BigCommerce (Stencil)

Detection: `.productView, [data-product-option-change]`.

| Field | Selector |
|---|---|
| title | `.productView-title` |
| price | `.productView-price .price, .price--withoutTax` |
| images | `.productView-image img, .productView-imageCarousel-main img` |
| description | `.productView-description, #tab-description` |

## Squarespace Commerce

Detection: `.ProductItem` or `body.squarespace-commerce`.

| Field | Selector |
|---|---|
| title | `.ProductItem-details-title` |
| price | `.product-price, .sqs-money-native` |
| images | `.ProductItem-gallery img` |
| description | `.ProductItem-details-excerpt, .ProductItem-product-description` |

## Generic heuristic fallback

When nothing else matches:
- title: `<h1>` first, else `meta[property="og:title"]`
- images: `meta[property="og:image"]` + `og:image:secure_url`
- description: `meta[property="og:description"]` or `meta[name="description"]`
- price: first `[itemprop="price"], [data-price], .price` match

Marks the product with tag `"heuristic"` so the mother agent can prompt the user for review.
