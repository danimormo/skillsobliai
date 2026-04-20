import axios from 'axios';
import * as cheerio from 'cheerio';
import { newStealthContext, detectCaptcha } from '../utils/browser.js';
import { pickUserAgent } from '../utils/userAgents.js';
import { preprocessImage, saveTempImage } from './imageHandler.js';
import { requestLogger } from '../utils/logger.js';
import type { Price } from '../types.js';

export interface UrlExtractionResult {
  /** Absolute path to preprocessed JPEG. */
  imagePath: string;
  title?: string;
  price?: Price;
  /** Raw main image URL picked from the page. */
  sourceImageUrl?: string;
  /** Final URL after redirects (matters for competitor Shopify links). */
  finalUrl: string;
  warnings: string[];
}

const IMAGE_URL_RE = /\.(?:jpe?g|png|webp|avif)(?:\?.*)?$/i;

/**
 * Fetch a product page with a stealth Playwright context, scrape the main image
 * and metadata, download the image, then run it through `preprocessImage`.
 *
 * Strategy:
 *   1. Navigate with realistic UA, wait `networkidle` (fallback: domcontentloaded)
 *   2. Try og:image → twitter:image → largest <img>
 *   3. Extract title from og:title → <h1> → <title>
 *   4. Extract price via schema.org / common data-* / currency regex
 *   5. Download image via Axios (cheaper than Playwright for binary fetch)
 */
export async function extractFromUrl(
  requestId: string,
  url: string,
): Promise<UrlExtractionResult> {
  const log = requestLogger(requestId).child({ stage: 'urlExtractor', url });
  const ctx = await newStealthContext();
  const page = await ctx.newPage();
  const warnings: string[] = [];

  try {
    const response = await page.goto(url, { waitUntil: 'domcontentloaded' });
    if (!response) throw new Error(`navigation failed: no response for ${url}`);
    const status = response.status();
    if (status === 404) throw new Error('page returned 404');
    if (status >= 500) throw new Error(`page returned ${status}`);

    // Best effort: give JS a moment, then bail on timeout (Shopify/React hydration).
    await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {
      warnings.push('networkidle not reached within 5s — page may be partially hydrated');
    });

    if (await detectCaptcha(page)) {
      throw new Error('captcha wall detected on source URL');
    }

    const finalUrl = page.url();
    const html = await page.content();
    const $ = cheerio.load(html);

    const sourceImageUrl = pickMainImage($, finalUrl);
    const title = pickTitle($);
    const price = pickPrice($, html);

    if (!sourceImageUrl) throw new Error('no main image found on page');

    log.debug({ sourceImageUrl, title, price }, 'extracted page metadata');

    const buffer = await downloadImage(sourceImageUrl, finalUrl);
    const rawPath = await saveTempImage(requestId, buffer, guessExt(sourceImageUrl));
    const pre = await preprocessImage({ requestId, imagePath: rawPath });
    warnings.push(...pre.warnings);

    return {
      imagePath: pre.imagePath,
      ...(title ? { title } : {}),
      ...(price ? { price } : {}),
      sourceImageUrl,
      finalUrl,
      warnings,
    };
  } finally {
    await ctx.close().catch(() => {});
  }
}

export function pickMainImage($: cheerio.CheerioAPI, base: string): string | undefined {
  const ogImage =
    $('meta[property="og:image:secure_url"]').attr('content') ||
    $('meta[property="og:image"]').attr('content') ||
    $('meta[name="twitter:image"]').attr('content');
  if (ogImage) return absolutize(ogImage, base);

  // JSON-LD Product.image (common on Shopify).
  const ld = $('script[type="application/ld+json"]')
    .toArray()
    .map((el) => $(el).text())
    .join('\n');
  const ldImg = /"image"\s*:\s*"([^"]+\.(?:jpe?g|png|webp))"/i.exec(ld)?.[1];
  if (ldImg) return absolutize(ldImg, base);

  // Largest <img> by width attribute (fallback).
  let best: { url: string; score: number } | undefined;
  $('img').each((_i, el) => {
    const src =
      $(el).attr('src') ||
      $(el).attr('data-src') ||
      $(el).attr('data-original') ||
      $(el).attr('srcset')?.split(',').pop()?.trim().split(' ')[0];
    if (!src || !IMAGE_URL_RE.test(src)) return;
    const w = Number($(el).attr('width') || 0);
    const h = Number($(el).attr('height') || 0);
    const score = (w || 0) * (h || 0) || (w || 0) + (h || 0);
    if (!best || score > best.score) best = { url: absolutize(src, base), score };
  });
  return best?.url;
}

export function pickTitle($: cheerio.CheerioAPI): string | undefined {
  const ogTitle = $('meta[property="og:title"]').attr('content')?.trim();
  if (ogTitle) return ogTitle;
  const h1 = $('h1').first().text().trim();
  if (h1) return h1;
  const docTitle = $('title').text().trim();
  return docTitle || undefined;
}

export function pickPrice($: cheerio.CheerioAPI, html: string): Price | undefined {
  // schema.org Offer.price
  const schemaPrice = $('[itemprop="price"]').attr('content') || $('[itemprop="price"]').text();
  const schemaCurr =
    $('[itemprop="priceCurrency"]').attr('content') || $('[itemprop="priceCurrency"]').text();
  if (schemaPrice) {
    const value = parsePrice(schemaPrice);
    if (value !== undefined) {
      return { value, currency: normalizeCurrency(schemaCurr) ?? 'USD' };
    }
  }

  // JSON-LD Offer.price
  const ldMatch =
    /"price"\s*:\s*"?([\d.,]+)"?[^}]*?"priceCurrency"\s*:\s*"([A-Z]{3})"/i.exec(html) ||
    /"priceCurrency"\s*:\s*"([A-Z]{3})"[^}]*?"price"\s*:\s*"?([\d.,]+)"?/i.exec(html);
  if (ldMatch) {
    const [p, c] =
      ldMatch.length === 3 && /^[A-Z]{3}$/.test(ldMatch[1]!)
        ? [ldMatch[2]!, ldMatch[1]!]
        : [ldMatch[1]!, ldMatch[2]!];
    const value = parsePrice(p);
    if (value !== undefined) return { value, currency: c };
  }

  // Heuristic: "$12.99" / "€ 9,50" / "¥199"
  const heuristic = /([€$£¥]|USD|EUR|GBP|CNY)\s?([\d]+[.,]?\d{0,2})/.exec(
    $('body').text().slice(0, 5000),
  );
  if (heuristic) {
    const value = parsePrice(heuristic[2]!);
    if (value !== undefined) {
      return { value, currency: symbolToIso(heuristic[1]!) };
    }
  }

  return undefined;
}

export function parsePrice(raw: string): number | undefined {
  const cleaned = raw.replace(/[^\d.,-]/g, '');
  if (!cleaned) return undefined;
  // Treat last '.' or ',' as decimal separator.
  const lastDot = cleaned.lastIndexOf('.');
  const lastComma = cleaned.lastIndexOf(',');
  let normalized = cleaned;
  if (lastDot > -1 && lastComma > -1) {
    if (lastComma > lastDot) normalized = cleaned.replace(/\./g, '').replace(',', '.');
    else normalized = cleaned.replace(/,/g, '');
  } else if (lastComma > -1) {
    normalized = cleaned.replace(',', '.');
  }
  const n = Number(normalized);
  return Number.isFinite(n) && n > 0 ? n : undefined;
}

function symbolToIso(sym: string): string {
  switch (sym) {
    case '$':
      return 'USD';
    case '€':
      return 'EUR';
    case '£':
      return 'GBP';
    case '¥':
      return 'CNY';
    default:
      return sym.toUpperCase();
  }
}

function normalizeCurrency(raw?: string): string | undefined {
  if (!raw) return undefined;
  const m = raw.trim().toUpperCase();
  return /^[A-Z]{3}$/.test(m) ? m : undefined;
}

function absolutize(src: string, base: string): string {
  try {
    return new URL(src, base).toString();
  } catch {
    return src;
  }
}

function guessExt(url: string): string {
  const m = /\.(jpe?g|png|webp|avif)(?:\?|$)/i.exec(url);
  return m ? m[1]!.toLowerCase() : 'jpg';
}

async function downloadImage(imageUrl: string, refererUrl: string): Promise<Buffer> {
  const res = await axios.get<ArrayBuffer>(imageUrl, {
    responseType: 'arraybuffer',
    timeout: 15000,
    maxRedirects: 5,
    headers: {
      'User-Agent': pickUserAgent(),
      Referer: refererUrl,
      Accept: 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
    },
  });
  const buf = Buffer.from(res.data);
  if (buf.length === 0) throw new Error(`empty image body at ${imageUrl}`);
  return buf;
}
