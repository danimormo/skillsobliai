import { log, originOf, safeJson } from './utils.js';

/**
 * @typedef {Object} RouteInfo
 * @property {'product'|'collection'|'homepage'} kind
 * @property {string} origin
 * @property {string|null} handle  Product or collection handle, null for homepage
 * @property {boolean} isShopify
 */

/**
 * Detect URL kind (product / collection / homepage).
 * @param {string} rawUrl
 * @returns {{ kind: 'product'|'collection'|'homepage', origin: string, handle: string|null }}
 */
export function classifyUrl(rawUrl) {
  const url = new URL(rawUrl);
  const origin = url.origin;
  const path = url.pathname.replace(/\/+$/, '');

  // /products/<handle> or /collections/<X>/products/<handle>
  const productMatch = path.match(/\/products\/([^/]+)/);
  if (productMatch) {
    return { kind: 'product', origin, handle: productMatch[1] };
  }

  const collectionMatch = path.match(/\/collections\/([^/]+)/);
  if (collectionMatch) {
    return { kind: 'collection', origin, handle: collectionMatch[1] };
  }

  if (path === '' || path === '/') {
    return { kind: 'homepage', origin, handle: null };
  }

  // Unknown path → treat as homepage and let the extractor figure it out
  return { kind: 'homepage', origin, handle: null };
}

/**
 * Check if the origin is a Shopify store by probing /products.json.
 * @param {string} origin
 * @returns {Promise<boolean>}
 */
export async function detectShopify(origin) {
  const probeUrl = `${origin}/products.json?limit=1`;
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    const res = await fetch(probeUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; ShopifyProductCloner/1.0)',
        Accept: 'application/json',
      },
      signal: controller.signal,
    });
    clearTimeout(timeout);
    if (!res.ok) return false;
    const text = await res.text();
    const json = safeJson(text);
    return !!(json && Array.isArray(json.products));
  } catch (err) {
    log.debug(`Shopify probe failed for ${origin}: ${err.message}`);
    return false;
  }
}

/**
 * Full route resolution: classify + Shopify detection.
 * @param {string} rawUrl
 * @returns {Promise<RouteInfo>}
 */
export async function resolveRoute(rawUrl) {
  const base = classifyUrl(rawUrl);
  const origin = base.origin || originOf(rawUrl);
  if (!origin) throw new Error(`Invalid URL: ${rawUrl}`);
  const isShopify = await detectShopify(origin);
  log.info(`Route: ${base.kind} on ${origin} (shopify=${isShopify})`);
  return { ...base, origin, isShopify };
}
