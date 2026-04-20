import slugifyLib from 'slugify';

/**
 * Structured stderr logger with [clone] prefix.
 * Never writes to stdout (stdout is reserved for the final JSON result).
 */
export const log = {
  info: (msg, meta) => process.stderr.write(`[clone] ${msg}${meta ? ' ' + JSON.stringify(meta) : ''}\n`),
  warn: (msg, meta) => process.stderr.write(`[clone] WARN ${msg}${meta ? ' ' + JSON.stringify(meta) : ''}\n`),
  error: (msg, meta) => process.stderr.write(`[clone] ERROR ${msg}${meta ? ' ' + JSON.stringify(meta) : ''}\n`),
  debug: (msg, meta) => {
    if (process.env.DEBUG) {
      process.stderr.write(`[clone] DEBUG ${msg}${meta ? ' ' + JSON.stringify(meta) : ''}\n`);
    }
  },
};

/**
 * Slugify a product title into a Shopify-safe handle.
 * @param {string} title
 * @returns {string} lowercase, dash-separated, max 80 chars, safe for URL
 */
export function toHandle(title) {
  if (!title) return `product-${Date.now()}`;
  const slug = slugifyLib(String(title), {
    lower: true,
    strict: true,
    trim: true,
  });
  return slug.slice(0, 80).replace(/-+$/, '') || `product-${Date.now()}`;
}

/**
 * Round a price according to the target market convention.
 * US/UK/CA/AU → .99; EU → .00 (default); FR/BE/NL → .95 as alt (we default to .00).
 * @param {number} value
 * @param {string} [market]
 * @returns {number}
 */
export function roundPrice(value, market) {
  if (!isFinite(value) || value <= 0) return 0;
  const floor = Math.floor(value);
  const usStyle = new Set(['US', 'UK', 'GB', 'CA', 'AU', 'NZ']);
  if (market && usStyle.has(market.toUpperCase())) {
    return Number((floor + 0.99).toFixed(2));
  }
  return Number(floor.toFixed(2));
}

/**
 * Truncate a title to N chars without cutting words mid-stream.
 * @param {string} title
 * @param {number} max
 * @returns {string}
 */
export function truncateTitle(title, max = 70) {
  if (!title) return '';
  if (title.length <= max) return title;
  const cut = title.slice(0, max);
  const lastSpace = cut.lastIndexOf(' ');
  return (lastSpace > 30 ? cut.slice(0, lastSpace) : cut).trim();
}

/**
 * Sanitize HTML description: remove scripts, iframes, inline event handlers, data: URIs.
 * Intentionally lightweight — full sanitization is overkill for Shopify which already sanitizes.
 * @param {string} html
 * @returns {string}
 */
export function sanitizeHtml(html) {
  if (!html) return '';
  return String(html)
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
    .replace(/\son\w+="[^"]*"/gi, '')
    .replace(/\son\w+='[^']*'/gi, '')
    .replace(/javascript:/gi, '');
}

/**
 * Sleep N milliseconds.
 * @param {number} ms
 */
export function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

/**
 * Parse JSON safely. Returns null on failure instead of throwing.
 */
export function safeJson(str) {
  try {
    return JSON.parse(str);
  } catch {
    return null;
  }
}

/**
 * Normalize a URL: strip trailing slash on path, remove query fragments we never need.
 * Keeps query strings because some stores require them (e.g. variants).
 */
export function normalizeUrl(u) {
  try {
    const url = new URL(u);
    url.hash = '';
    return url.toString();
  } catch {
    return u;
  }
}

/**
 * Extract the origin (scheme + host) of a URL.
 */
export function originOf(u) {
  try {
    return new URL(u).origin;
  } catch {
    return null;
  }
}

/**
 * Retry an async function with exponential backoff.
 * @param {() => Promise<any>} fn
 * @param {{ retries?: number, baseMs?: number, maxMs?: number, onRetry?: (e, attempt) => void }} [opts]
 */
export async function retry(fn, opts = {}) {
  const { retries = 5, baseMs = 1000, maxMs = 30000, onRetry } = opts;
  let attempt = 0;
  let lastErr;
  while (attempt <= retries) {
    try {
      return await fn();
    } catch (err) {
      lastErr = err;
      if (attempt === retries) break;
      const delay = Math.min(maxMs, baseMs * Math.pow(2, attempt));
      if (onRetry) onRetry(err, attempt + 1);
      await sleep(delay);
      attempt++;
    }
  }
  throw lastErr;
}
