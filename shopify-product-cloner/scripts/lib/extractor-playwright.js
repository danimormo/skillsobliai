import * as cheerio from 'cheerio';
import { log, normalizeUrl } from './utils.js';
import { extractFromJsonLd } from './extractor-jsonld.js';

let _browserPromise = null;

async function getBrowser() {
  if (!_browserPromise) {
    const { chromium } = await import('playwright');
    _browserPromise = chromium.launch({ headless: true });
  }
  return _browserPromise;
}

/** Close the singleton browser if open. Safe to call even if never launched. */
export async function closePlaywright() {
  if (_browserPromise) {
    try {
      const b = await _browserPromise;
      await b.close();
    } catch {}
    _browserPromise = null;
  }
}

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36';

async function newPage() {
  const browser = await getBrowser();
  const context = await browser.newContext({
    userAgent: UA,
    viewport: { width: 1440, height: 900 },
    locale: 'en-US',
  });
  const page = await context.newPage();
  return { page, context };
}

/**
 * Fetch a URL's rendered HTML via Playwright.
 * @param {string} url
 * @param {number} [timeoutMs]
 * @returns {Promise<string>}
 */
async function fetchRenderedHtml(url, timeoutMs = 30000) {
  const { page, context } = await newPage();
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: timeoutMs });
    // Best-effort: wait for network idle-ish or a JSON-LD script
    await page.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => {});
    const html = await page.content();
    return html;
  } finally {
    await context.close();
  }
}

/** Platform-specific selectors. Ordered by specificity. */
const PLATFORM_SELECTORS = [
  // WooCommerce
  {
    name: 'woocommerce',
    test: ($) => $('body.woocommerce, body.woocommerce-page, .woocommerce-product-gallery').length > 0,
    title: 'h1.product_title, .product_title',
    price: '.price .woocommerce-Price-amount.amount',
    images: '.woocommerce-product-gallery__image img, .woocommerce-product-gallery__image a',
    description: '.woocommerce-product-details__short-description, #tab-description, .woocommerce-Tabs-panel--description',
  },
  // Magento
  {
    name: 'magento',
    test: ($) => $('.product-info-main, .catalog-product-view').length > 0,
    title: '.product-info-main .page-title .base, h1.page-title span',
    price: '.product-info-main .price, [data-price-type="finalPrice"] .price',
    images: '.fotorama__stage__frame img, .gallery-placeholder img, .product.media img',
    description: '.product.attribute.description .value, #description',
  },
  // BigCommerce (Stencil)
  {
    name: 'bigcommerce',
    test: ($) => $('.productView, [data-product-option-change]').length > 0,
    title: '.productView-title',
    price: '.productView-price .price, .price--withoutTax',
    images: '.productView-image img, .productView-imageCarousel-main img',
    description: '.productView-description, #tab-description',
  },
  // Squarespace
  {
    name: 'squarespace',
    test: ($) => $('.ProductItem, .sqs-block-product, body.squarespace-commerce').length > 0,
    title: '.ProductItem-details .ProductItem-details-title, h1.ProductItem-details-title',
    price: '.product-price, .sqs-money-native',
    images: '.ProductItem-gallery img, .ProductItem-gallery-slides-item-image',
    description: '.ProductItem-details-excerpt, .ProductItem-product-description',
  },
];

/**
 * Fallback extraction using Cheerio + platform-aware selectors.
 * @param {string} html
 * @param {string} sourceUrl
 */
function extractFromSelectors(html, sourceUrl) {
  const $ = cheerio.load(html);
  const platform = PLATFORM_SELECTORS.find((p) => p.test($));
  if (!platform) return null;

  const title = $(platform.title).first().text().trim();
  if (!title) return null;

  const priceText = $(platform.price).first().text().trim();
  const priceMatch = priceText.match(/[\d.,]+/);
  const price = priceMatch ? parseFloat(priceMatch[0].replace(/,(\d{3})/g, '$1').replace(',', '.')) : 0;

  const images = [];
  $(platform.images).each((i, el) => {
    const src = $(el).attr('src') || $(el).attr('data-src') || $(el).attr('href') || $(el).attr('data-zoom-image');
    if (src && /^https?:/.test(src)) {
      images.push({ src, position: images.length + 1 });
    }
  });

  const description = $(platform.description).first().html() || '';

  log.info(`Extracted via ${platform.name} selectors: "${title}"`);

  return {
    sourceUrl,
    title,
    bodyHtml: description,
    vendor: null,
    productType: null,
    tags: [platform.name],
    optionNames: [],
    variants: [{ title: 'Default', price, sku: null, selectedOptions: [] }],
    images,
    sourceLanguage: null,
  };
}

/**
 * Ultra-generic heuristic fallback: h1 + og:image + first price-looking text.
 */
function extractHeuristic(html, sourceUrl) {
  const $ = cheerio.load(html);
  const title = ($('h1').first().text().trim() || $('meta[property="og:title"]').attr('content') || '').trim();
  if (!title) return null;

  const ogImages = [];
  $('meta[property="og:image"], meta[property="og:image:url"], meta[property="og:image:secure_url"]').each((_, el) => {
    const c = $(el).attr('content');
    if (c) ogImages.push({ src: c, position: ogImages.length + 1 });
  });

  const desc = $('meta[property="og:description"]').attr('content') || $('meta[name="description"]').attr('content') || '';
  const priceText = $('[itemprop="price"], [data-price], .price').first().text();
  const priceMatch = (priceText || '').match(/([\d]+[.,]?[\d]*)/);
  const price = priceMatch ? parseFloat(priceMatch[1].replace(',', '.')) : 0;

  log.warn(`Heuristic fallback extraction for "${title}" — data may be incomplete`);

  return {
    sourceUrl,
    title,
    bodyHtml: desc ? `<p>${desc}</p>` : '',
    vendor: null,
    productType: null,
    tags: ['heuristic'],
    optionNames: [],
    variants: [{ title: 'Default', price, sku: null, selectedOptions: [] }],
    images: ogImages,
    sourceLanguage: null,
  };
}

/**
 * Extract a single product page using Playwright + JSON-LD + selectors fallback.
 * @param {string} sourceUrl
 * @returns {Promise<import('./extractor-shopify.js').ExtractedProduct>}
 */
export async function extractPlaywrightProduct(sourceUrl) {
  log.info(`Rendering with Playwright: ${sourceUrl}`);
  const html = await fetchRenderedHtml(sourceUrl);

  const fromJsonLd = extractFromJsonLd(html, sourceUrl);
  if (fromJsonLd && fromJsonLd.images.length > 0) return fromJsonLd;

  const fromSelectors = extractFromSelectors(html, sourceUrl);
  if (fromSelectors) return fromSelectors;

  if (fromJsonLd) return fromJsonLd; // JSON-LD without images still better than heuristic

  const heuristic = extractHeuristic(html, sourceUrl);
  if (heuristic) return heuristic;

  throw new Error(`Extraction failed: no JSON-LD and no matching selectors for ${sourceUrl}`);
}

/**
 * Extract product links from a collection or homepage, then fetch each product.
 * @param {string} listingUrl
 * @param {number} maxProducts
 * @returns {Promise<import('./extractor-shopify.js').ExtractedProduct[]>}
 */
export async function extractPlaywrightListing(listingUrl, maxProducts = 100) {
  log.info(`Rendering listing: ${listingUrl}`);
  const html = await fetchRenderedHtml(listingUrl);
  const $ = cheerio.load(html);
  const origin = new URL(listingUrl).origin;

  const links = new Set();
  $('a[href]').each((_, el) => {
    const href = $(el).attr('href') || '';
    if (!href) return;
    if (/\/products?\/[^/?#]+/i.test(href) || /\/product\/[^/?#]+/i.test(href) || /-p-\d+\.html/.test(href)) {
      try {
        const abs = new URL(href, listingUrl).toString();
        if (new URL(abs).origin === origin) {
          links.add(normalizeUrl(abs));
        }
      } catch {}
    }
  });

  const unique = [...links].slice(0, maxProducts);
  log.info(`Found ${unique.length} product links on ${listingUrl}`);

  const out = [];
  for (const url of unique) {
    try {
      const p = await extractPlaywrightProduct(url);
      out.push(p);
    } catch (err) {
      log.warn(`Listing item failed: ${url} → ${err.message}`);
    }
  }
  return out;
}
