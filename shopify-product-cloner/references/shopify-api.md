# Shopify Admin API — quick reference

This skill uses **Admin GraphQL API 2025-10**. REST is kept only for edge cases; prefer GraphQL.

## Endpoints

- GraphQL: `POST https://<shop>/admin/api/2025-10/graphql.json`
- REST:    `https://<shop>/admin/api/2025-10/...`
- Auth:    `X-Shopify-Access-Token: <admin-api-access-token>`
- Required scopes: `write_products`, `read_products`, `write_files`, `write_publications` (if assigning to collections).

## Rate limits

- REST: **2 req/sec** (standard plan), 40 bucket size.
- GraphQL: **100 cost points/sec** restore (standard), 1000 bucket. Every response contains:
  ```json
  "extensions": { "cost": { "requestedQueryCost": 11, "throttleStatus": { "currentlyAvailable": 988, "maximumAvailable": 1000, "restoreRate": 100 } } }
  ```
  We inspect `currentlyAvailable` and pre-pause when below 100.
- Handle `429` / `430` by honoring `Retry-After`; exponential backoff otherwise.

## Mutations used

### productCreate

```graphql
mutation CreateProduct($input: ProductCreateInput!) {
  productCreate(product: $input) {
    product { id handle title }
    userErrors { field message }
  }
}
```

`ProductCreateInput` (subset we use):

```json
{
  "title": "string",
  "handle": "string",
  "descriptionHtml": "string",
  "vendor": "string",
  "productType": "string",
  "tags": ["string"],
  "status": "ACTIVE | DRAFT",
  "productOptions": [ { "name": "Size", "values": [{ "name": "S" }, { "name": "M" }] } ]
}
```

Notes on 2025-10:
- `productCreate` creates the product with options but NOT variants beyond the default one. Use `productVariantsBulkCreate` after for the real variants.
- `handle` must be unique within the shop — our dedup check runs first.

### productVariantsBulkCreate

```graphql
mutation BulkCreateVariants($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkCreate(productId: $productId, variants: $variants) {
    productVariants { id title sku }
    userErrors { field message }
  }
}
```

`ProductVariantsBulkInput`:

```json
{
  "price": "29.99",
  "compareAtPrice": "38.99",
  "sku": "ABC-123",
  "optionValues": [ { "optionName": "Size", "name": "S" }, { "optionName": "Color", "name": "Black" } ],
  "inventoryItem": { "measurement": { "weight": { "value": 0.5, "unit": "KILOGRAMS" } } }
}
```

### metafieldsSet

```graphql
mutation MfSet($metafields: [MetafieldsSetInput!]!) {
  metafieldsSet(metafields: $metafields) {
    metafields { id key namespace }
    userErrors { field message }
  }
}
```

We store:
- `custom.source_url` → original source URL (for dedup)
- `global.description_tag` → SEO meta description

### stagedUploadsCreate

```graphql
mutation StagedUploads($input: [StagedUploadInput!]!) {
  stagedUploadsCreate(input: $input) {
    stagedTargets { url resourceUrl parameters { name value } }
    userErrors { field message }
  }
}
```

- If `parameters` is non-empty → upload via **POST multipart form-data** to `url` (AWS S3-style).
- If `parameters` empty → upload via **PUT** to `url` with `Content-Type` + `Content-Length`.
- Use the returned `resourceUrl` as `originalSource` when creating media.

### productCreateMedia

```graphql
mutation ProductCreateMedia($productId: ID!, $media: [CreateMediaInput!]!) {
  productCreateMedia(productId: $productId, media: $media) {
    media { ... on MediaImage { id alt image { url } } }
    mediaUserErrors { field message }
  }
}
```

`CreateMediaInput`:
```json
{ "originalSource": "<target.resourceUrl>", "alt": "Nike Air Max 90 - image 2", "mediaContentType": "IMAGE" }
```

### collectionAddProducts

```graphql
mutation AddProductsToCol($id: ID!, $productIds: [ID!]!) {
  collectionAddProducts(id: $id, productIds: $productIds) {
    collection { id }
    userErrors { field message }
  }
}
```

Collections must be **manual** (not smart/rule-based) to accept `collectionAddProducts`. If a smart collection, the product will match only if it satisfies the rules.

## Dedup queries

### productByHandle

```graphql
query FindByHandle($handle: String!) { productByHandle(handle: $handle) { id handle } }
```

### Search by metafield

```graphql
query FindBySource($q: String!) {
  products(first: 5, query: $q) {
    edges { node { id handle metafield(namespace: "custom", key: "source_url") { value } } }
  }
}
```

Query string: `metafield_custom_source_url:'<url>'`.

## GIDs

All IDs used in GraphQL are GIDs: `gid://shopify/Product/1234567890`, `gid://shopify/Collection/...`. Never pass numeric IDs to GraphQL.
