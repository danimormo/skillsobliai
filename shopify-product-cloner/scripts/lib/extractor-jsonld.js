import * as cheerio from 'cheerio';
import { log, safeJson } from './utils.js';

/**
 * Parse JSON-LD schema.org/Product blocks from raw HTML.
 * Returns the first Product (or ProductGroup) node found, or null.
 * @param {string} html
 * @returns {object|null}
 */
export function parseJsonLd(html) {
  const $ = cheerio.load(html);
  const candidates = [];
  $('script[type="application/ld+json"]').each((_, el) => {
    const raw = $(el).contents().text();
    if (!raw) return;
    const parsed = safeJson(raw);
    if (!parsed) return;
    // Flatten @graph / arrays
    const items = Array.isArray(parsed)
      ? parsed
      : parsed['@graph'] && Array.isArray(parsed['@graph'])
        ? parsed['@graph']
        : [parsed];
    for (const item of items) {
      if (!item || !item['@type']) continue;
      const types = Array.isArray(item['@type']) ? item['@type'] : [item['@type']];
      if (types.some((t) => /Product/i.test(t))) {
        candidates.push(item);
      }
    }
  });
  if (!candidates.length) return null;
  // Prefer the one with most data
  candidates.sort((a, b) => Object.keys(b).length - Object.keys(a).length);
  return candidates[0];
}

/**
 * Normalize a JSON-LD Product node into our ExtractedProduct shape.
 * @param {object} node
 * @param {string} sourceUrl
 * @returns {import('./extractor-shopify.js').ExtractedProduct|null}
 */
export function jsonLdToProduct(node, sourceUrl) {
  if (!node) return null;
  const title = node.name || null;
  if (!title) return null;

  const bodyHtml = node.description ? `<p>${String(node.description).replace(/\n/g, '</p><p>')}</p>` : '';
  const vendor = node.brand
    ? typeof node.brand === 'string'
      ? node.brand
      : node.brand.name || null
    : null;
  const productType = node.category
    ? typeof node.category === 'string'
      ? node.category
      : null
    : null;

  const imagesRaw = Array.isArray(node.image) ? node.image : node.image ? [node.image] : [];
  const images = imagesRaw
    .map((img, i) => {
      if (typeof img === 'string') return { src: img, position: i + 1 };
      if (img && img.url) return { src: img.url, alt: img.caption, position: i + 1 };
      return null;
    })
    .filter(Boolean);

  /** Offers → variants */
  const offers = node.offers
    ? Array.isArray(node.offers)
      ? node.offers
      : node.offers['@type'] === 'AggregateOffer'
        ? []
        : [node.offers]
    : [];

  const variants = [];

  if (Array.isArray(node.hasVariant) && node.hasVariant.length) {
    for (const v of node.hasVariant) {
      const vOffers = v.offers
        ? Array.isArray(v.offers)
          ? v.offers
          : [v.offers]
        : [];
      const price = vOffers[0] ? parseFloat(vOffers[0].price) : 0;
      const selectedOptions = [];
      if (v.color) selectedOptions.push({ name: 'Color', value: String(v.color) });
      if (v.size) selectedOptions.push({ name: 'Size', value: String(v.size) });
      if (v.material) selectedOptions.push({ name: 'Material', value: String(v.material) });
      variants.push({
        title: v.name || 'Default',
        price: isFinite(price) ? price : 0,
        sku: v.sku || null,
        selectedOptions,
      });
    }
  } else if (offers.length) {
    for (const o of offers) {
      variants.push({
        title: 'Default',
        price: parseFloat(o.price) || 0,
        sku: node.sku || o.sku || null,
        selectedOptions: [],
      });
    }
  } else {
    variants.push({ title: 'Default', price: 0, sku: node.sku || null, selectedOptions: [] });
  }

  // Derive option names from distinct selectedOptions across variants
  const optNames = new Set();
  variants.forEach((v) => v.selectedOptions.forEach((o) => optNames.add(o.name)));
  const optionNames = [...optNames];

  return {
    sourceUrl,
    title: String(title).trim(),
    bodyHtml,
    vendor,
    productType,
    tags: [],
    optionNames,
    variants,
    images,
    sourceLanguage: null,
  };
}

/**
 * Given raw HTML + sourceUrl, attempt to extract a product entirely from JSON-LD.
 * @param {string} html
 * @param {string} sourceUrl
 * @returns {import('./extractor-shopify.js').ExtractedProduct|null}
 */
export function extractFromJsonLd(html, sourceUrl) {
  const node = parseJsonLd(html);
  if (!node) {
    log.debug('No JSON-LD Product block found');
    return null;
  }
  const product = jsonLdToProduct(node, sourceUrl);
  if (product) log.info(`Extracted from JSON-LD: "${product.title}" (${product.images.length} images, ${product.variants.length} variants)`);
  return product;
}
