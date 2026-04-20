import PQueue from 'p-queue';
import { log, sleep, retry } from './utils.js';

/**
 * Shopify Admin API client with GraphQL-first, REST fallback, and rate limiting.
 */
export class ShopifyClient {
  /**
   * @param {{ shop: string, accessToken: string, apiVersion?: string }} cfg
   */
  constructor({ shop, accessToken, apiVersion = '2025-10' }) {
    if (!shop || !accessToken) throw new Error('ShopifyClient requires shop + accessToken');
    this.shop = shop.replace(/^https?:\/\//, '').replace(/\/+$/, '');
    this.accessToken = accessToken;
    this.apiVersion = apiVersion;
    // GraphQL leaky bucket: 100 points/sec for standard Shopify plan. We self-throttle below.
    this.gqlQueue = new PQueue({ concurrency: 2, intervalCap: 2, interval: 1000 });
    // REST: 2 req/sec standard plan.
    this.restQueue = new PQueue({ concurrency: 1, intervalCap: 2, interval: 1000 });
    this._gqlAvailable = 1000;
  }

  get graphqlUrl() {
    return `https://${this.shop}/admin/api/${this.apiVersion}/graphql.json`;
  }

  get restBase() {
    return `https://${this.shop}/admin/api/${this.apiVersion}`;
  }

  /** Common headers */
  _headers(extra = {}) {
    return {
      'X-Shopify-Access-Token': this.accessToken,
      'Content-Type': 'application/json',
      Accept: 'application/json',
      ...extra,
    };
  }

  /**
   * Execute a GraphQL query/mutation with retry + throttle awareness.
   * @param {string} query
   * @param {object} [variables]
   * @returns {Promise<any>}
   */
  async graphql(query, variables = {}) {
    return this.gqlQueue.add(() =>
      retry(
        async () => {
          // If we know we're low on points, pre-pause
          if (this._gqlAvailable < 100) {
            await sleep(1000);
          }
          const res = await fetch(this.graphqlUrl, {
            method: 'POST',
            headers: this._headers(),
            body: JSON.stringify({ query, variables }),
          });

          if (res.status === 429 || res.status === 430) {
            const ra = parseInt(res.headers.get('retry-after') || '2', 10);
            log.warn(`GraphQL throttled (${res.status}), retry-after=${ra}s`);
            await sleep(ra * 1000);
            throw new Error(`Throttled ${res.status}`);
          }
          if (res.status >= 500) {
            throw new Error(`Shopify 5xx: ${res.status}`);
          }
          if (!res.ok) {
            const body = await res.text();
            throw new Error(`GraphQL HTTP ${res.status}: ${body.slice(0, 500)}`);
          }
          const json = await res.json();
          if (json.extensions?.cost?.throttleStatus) {
            this._gqlAvailable = json.extensions.cost.throttleStatus.currentlyAvailable;
          }
          if (json.errors && json.errors.length) {
            const msg = json.errors.map((e) => e.message).join('; ');
            throw new Error(`GraphQL error: ${msg}`);
          }
          return json.data;
        },
        {
          retries: 5,
          baseMs: 1000,
          maxMs: 30000,
          onRetry: (e, n) => log.warn(`GraphQL retry ${n}: ${e.message}`),
        }
      )
    );
  }

  /**
   * Execute a REST call with retry + throttle. Low-level — prefer graphql().
   */
  async rest(method, path, body = null) {
    return this.restQueue.add(() =>
      retry(
        async () => {
          const res = await fetch(`${this.restBase}${path}`, {
            method,
            headers: this._headers(),
            body: body ? JSON.stringify(body) : undefined,
          });
          if (res.status === 429) {
            const ra = parseInt(res.headers.get('retry-after') || '2', 10);
            await sleep(ra * 1000);
            throw new Error('REST 429 throttled');
          }
          if (res.status >= 500) throw new Error(`REST 5xx: ${res.status}`);
          if (!res.ok) {
            const t = await res.text();
            throw new Error(`REST ${method} ${path} failed: ${res.status} ${t.slice(0, 300)}`);
          }
          if (res.status === 204) return null;
          return res.json();
        },
        {
          retries: 5,
          baseMs: 1000,
          maxMs: 30000,
          onRetry: (e, n) => log.warn(`REST retry ${n}: ${e.message}`),
        }
      )
    );
  }

  // ---------- High-level helpers ----------

  /**
   * Search for a product by handle. Returns { id, handle } or null.
   */
  async findProductByHandle(handle) {
    // 2025-10: productByIdentifier replaces the deprecated productByHandle.
    const q = `
      query FindByHandle($identifier: ProductIdentifierInput!) {
        productByIdentifier(identifier: $identifier) { id handle }
      }`;
    const data = await this.graphql(q, { identifier: { handle } });
    return data?.productByIdentifier || null;
  }

  /**
   * Search for a product by the custom.source_url metafield.
   * Uses the productByIdentifier / products query with metafield filter where possible.
   */
  async findProductBySourceUrl(sourceUrl) {
    // `products` query supports tags & title — metafield search requires GraphQL search syntax
    // Shopify's search does index metafields as `metafield_custom_source_url:VALUE` on recent API versions.
    const q = `
      query FindBySource($q: String!) {
        products(first: 5, query: $q) {
          edges { node { id handle metafield(namespace: "custom", key: "source_url") { value } } }
        }
      }`;
    const queryString = `metafield_custom_source_url:'${sourceUrl.replace(/'/g, "\\'")}'`;
    const data = await this.graphql(q, { q: queryString });
    const edges = data?.products?.edges || [];
    const match = edges.find((e) => e.node?.metafield?.value === sourceUrl);
    return match ? { id: match.node.id, handle: match.node.handle } : null;
  }

  /**
   * Create a product via productCreate mutation.
   * @param {object} input  productCreate input
   * @returns {Promise<{id:string, handle:string}>}
   */
  async createProduct(input) {
    const m = `
      mutation CreateProduct($input: ProductCreateInput!) {
        productCreate(product: $input) {
          product { id handle title }
          userErrors { field message }
        }
      }`;
    const data = await this.graphql(m, { input });
    const errs = data?.productCreate?.userErrors || [];
    if (errs.length) throw new Error(`productCreate userErrors: ${JSON.stringify(errs)}`);
    const p = data?.productCreate?.product;
    if (!p) throw new Error('productCreate returned no product');
    return p;
  }

  /**
   * Bulk create variants (after productCreate) using productVariantsBulkCreate.
   * @param {string} productId
   * @param {Array<object>} variants  ProductVariantsBulkInput
   */
  async createVariants(productId, variants) {
    if (!variants || !variants.length) return [];
    const m = `
      mutation BulkCreateVariants($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
        productVariantsBulkCreate(productId: $productId, variants: $variants) {
          productVariants { id title sku }
          userErrors { field message }
        }
      }`;
    const data = await this.graphql(m, { productId, variants });
    const errs = data?.productVariantsBulkCreate?.userErrors || [];
    if (errs.length) log.warn(`productVariantsBulkCreate userErrors: ${JSON.stringify(errs)}`);
    return data?.productVariantsBulkCreate?.productVariants || [];
  }

  /**
   * Set a metafield on any resource (uses metafieldsSet).
   */
  async setMetafield(ownerId, namespace, key, value, type = 'single_line_text_field') {
    const m = `
      mutation MfSet($metafields: [MetafieldsSetInput!]!) {
        metafieldsSet(metafields: $metafields) {
          metafields { id key namespace }
          userErrors { field message }
        }
      }`;
    const data = await this.graphql(m, {
      metafields: [{ ownerId, namespace, key, value, type }],
    });
    const errs = data?.metafieldsSet?.userErrors || [];
    if (errs.length) log.warn(`metafieldsSet userErrors: ${JSON.stringify(errs)}`);
  }

  /**
   * Add a product to a collection by collection handle.
   */
  async addToCollectionByHandle(productId, collectionHandle) {
    const qCol = `
      query ColByHandle($handle: String!) {
        collections(first: 1, query: $handle) { edges { node { id handle } } }
      }`;
    const colRes = await this.graphql(qCol, { handle: `handle:${collectionHandle}` });
    const edge = colRes?.collections?.edges?.find((e) => e.node?.handle === collectionHandle);
    const colId = edge?.node?.id;
    if (!colId) {
      log.warn(`Collection not found: ${collectionHandle} — skipping assignment`);
      return;
    }
    const m = `
      mutation AddProductsToCol($id: ID!, $productIds: [ID!]!) {
        collectionAddProducts(id: $id, productIds: $productIds) {
          collection { id }
          userErrors { field message }
        }
      }`;
    const data = await this.graphql(m, { id: colId, productIds: [productId] });
    const errs = data?.collectionAddProducts?.userErrors || [];
    if (errs.length) log.warn(`collectionAddProducts userErrors: ${JSON.stringify(errs)}`);
  }

  /**
   * Initiate a stagedUploadsCreate for a single file.
   * @param {{ filename: string, mimeType: string, fileSize: string, httpMethod?: 'POST'|'PUT', resource?: string }} opts
   * @returns {Promise<{url: string, resourceUrl: string, parameters: Array<{name:string,value:string}>}>}
   */
  async stagedUploadCreate(opts) {
    const m = `
      mutation StagedUploads($input: [StagedUploadInput!]!) {
        stagedUploadsCreate(input: $input) {
          stagedTargets { url resourceUrl parameters { name value } }
          userErrors { field message }
        }
      }`;
    const input = [
      {
        filename: opts.filename,
        mimeType: opts.mimeType,
        httpMethod: opts.httpMethod || 'POST',
        resource: opts.resource || 'IMAGE',
        fileSize: String(opts.fileSize),
      },
    ];
    const data = await this.graphql(m, { input });
    const errs = data?.stagedUploadsCreate?.userErrors || [];
    if (errs.length) throw new Error(`stagedUploadsCreate: ${JSON.stringify(errs)}`);
    const target = data?.stagedUploadsCreate?.stagedTargets?.[0];
    if (!target) throw new Error('stagedUploadsCreate returned no target');
    return target;
  }

  /**
   * Attach already-uploaded media (by resourceUrl) to a product.
   * @param {string} productId
   * @param {Array<{ originalSource: string, alt?: string, mediaContentType?: 'IMAGE' }>} media
   */
  async productCreateMedia(productId, media) {
    if (!media || !media.length) return [];
    const m = `
      mutation ProductCreateMedia($productId: ID!, $media: [CreateMediaInput!]!) {
        productCreateMedia(productId: $productId, media: $media) {
          media { ... on MediaImage { id alt image { url } } }
          mediaUserErrors { field message }
        }
      }`;
    const input = media.map((it) => ({
      originalSource: it.originalSource,
      alt: it.alt || '',
      mediaContentType: it.mediaContentType || 'IMAGE',
    }));
    const data = await this.graphql(m, { productId, media: input });
    const errs = data?.productCreateMedia?.mediaUserErrors || [];
    if (errs.length) log.warn(`productCreateMedia userErrors: ${JSON.stringify(errs)}`);
    return data?.productCreateMedia?.media || [];
  }
}
