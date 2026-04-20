import { log, retry, safeJson } from './utils.js';

const UA = 'Mozilla/5.0 (compatible; ShopifyProductCloner/1.0)';
const DEFAULT_HEADERS = { 'User-Agent': UA, Accept: 'application/json' };

/**
 * @typedef {Object} ExtractedVariant
 * @property {string} title
 * @property {number} price
 * @property {number} [compareAtPrice]
 * @property {string|null} sku
 * @property {Array<{name: string, value: string}>} selectedOptions
 * @property {number} [weight]
 * @property {string} [weightUnit]
 * @property {number} [inventoryQuantity]
 *
 * @typedef {Object} ExtractedImage
 * @property {string} src
 * @property {string} [alt]
 * @property {number} [position]
 *
 * @typedef {Object} ExtractedProduct
 * @property {string} sourceUrl
 * @property {string} title
 * @property {string} bodyHtml
 * @property {string|null} vendor
 * @property {string|null} productType
 * @property {string[]} tags
 * @property {string[]} optionNames
 * @property {ExtractedVariant[]} variants
 * @property {ExtractedImage[]} images
 * @property {string|null} sourceLanguage
 */

async function getJson(url) {
  return retry(
    async () => {
      const res = await fetch(url, { headers: DEFAULT_HEADERS });
      if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
      const text = await res.text();
      const json = safeJson(text);
      if (!json) throw new Error(`Invalid JSON from ${url}`);
      return json;
    },
    { retries: 3, baseMs: 500, maxMs: 5000, onRetry: (e, n) => log.warn(`retry ${n} for ${url}: ${e.message}`) }
  );
}

/**
 * Normalize a raw Shopify /products.json product into our ExtractedProduct shape.
 * @param {object} raw
 * @param {string} origin
 * @returns {ExtractedProduct}
 */
function normalize(raw, origin) {
  const optionNames = (raw.options || []).map((o) => o.name);

  const variants = (raw.variants || []).map((v) => {
    const selectedOptions = [];
    [1, 2, 3].forEach((i) => {
      const name = optionNames[i - 1];
      const value = v[`option${i}`];
      if (name && value) selectedOptions.push({ name, value });
    });
    return {
      title: v.title,
      price: parseFloat(v.price) || 0,
      compareAtPrice: v.compare_at_price ? parseFloat(v.compare_at_price) : undefined,
      sku: v.sku || null,
      selectedOptions,
      weight: v.grams ? v.grams / 1000 : undefined,
      weightUnit: v.grams ? 'KILOGRAMS' : undefined,
      inventoryQuantity: typeof v.inventory_quantity === 'number' ? v.inventory_quantity : undefined,
    };
  });

  const images = (raw.images || []).map((img, i) => ({
    src: img.src,
    alt: img.alt || undefined,
    position: img.position || i + 1,
  }));

  const tags = typeof raw.tags === 'string'
    ? raw.tags.split(',').map((t) => t.trim()).filter(Boolean)
    : Array.isArray(raw.tags)
      ? raw.tags
      : [];

  return {
    sourceUrl: `${origin}/products/${raw.handle}`,
    title: raw.title,
    bodyHtml: raw.body_html || '',
    vendor: raw.vendor || null,
    productType: raw.product_type || null,
    tags,
    optionNames,
    variants,
    images,
    sourceLanguage: null,
  };
}

/**
 * Extract a single product from a Shopify store.
 * @param {string} origin
 * @param {string} handle
 * @returns {Promise<ExtractedProduct>}
 */
export async function extractShopifyProduct(origin, handle) {
  const url = `${origin}/products/${handle}.json`;
  log.info(`Fetching Shopify product JSON: ${url}`);
  const json = await getJson(url);
  if (!json.product) throw new Error(`No product in response for ${url}`);
  return normalize(json.product, origin);
}

/**
 * Extract all products from a Shopify collection (paginated).
 * @param {string} origin
 * @param {string} collectionHandle
 * @param {number} maxProducts
 * @returns {Promise<ExtractedProduct[]>}
 */
export async function extractShopifyCollection(origin, collectionHandle, maxProducts = 100) {
  const out = [];
  let page = 1;
  while (out.length < maxProducts) {
    const url = `${origin}/collections/${collectionHandle}/products.json?limit=250&page=${page}`;
    log.info(`Fetching Shopify collection page: ${url}`);
    const json = await getJson(url);
    const products = json.products || [];
    if (products.length === 0) break;
    for (const p of products) {
      out.push(normalize(p, origin));
      if (out.length >= maxProducts) break;
    }
    if (products.length < 250) break;
    page++;
  }
  return out;
}

/**
 * Extract all products from a Shopify store homepage (paginated /products.json).
 * @param {string} origin
 * @param {number} maxProducts
 * @returns {Promise<ExtractedProduct[]>}
 */
export async function extractShopifyHomepage(origin, maxProducts = 100) {
  const out = [];
  let page = 1;
  while (out.length < maxProducts) {
    const url = `${origin}/products.json?limit=250&page=${page}`;
    log.info(`Fetching Shopify store page: ${url}`);
    const json = await getJson(url);
    const products = json.products || [];
    if (products.length === 0) break;
    for (const p of products) {
      out.push(normalize(p, origin));
      if (out.length >= maxProducts) break;
    }
    if (products.length < 250) break;
    page++;
  }
  return out;
}
