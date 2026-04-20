import axios from 'axios';
import * as cheerio from 'cheerio';
import path from 'node:path';
import os from 'node:os';
import { mkdir, writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { pickUserAgent } from '../utils/userAgents.js';
import { embedImage, similarityScore } from '../matching/clipSimilarity.js';
import { titleScore as textTitleScore, keywordHitRate } from '../matching/textSimilarity.js';
import type { SupplierListing } from '../types.js';

/**
 * Shared PDP helpers used by every supplier integration.
 *
 * The philosophy is: suppliers vary mostly in URL shape and selector set.
 * The *procedure* (render → extract → normalize → validate) is identical.
 * Centralizing it here keeps each supplier module ~80 lines instead of 300
 * and gives us one place to fix resilience bugs.
 */

export interface PriceLike {
  value: number;
  currency: string;
}

/**
 * Multi-strategy price extractor. Tries, in order:
 *   1. JSON-LD Offer.price
 *   2. schema.org `[itemprop=price]`
 *   3. meta og:price:amount
 *   4. currency-symbol regex on the first 10KB of text
 *
 * Returns undefined when none of the strategies agree on a positive number —
 * better to return no price than a hallucinated one.
 */
export function extractPrice(html: string, $: cheerio.CheerioAPI): PriceLike | undefined {
  // JSON-LD Offer
  const lds = $('script[type="application/ld+json"]')
    .toArray()
    .map((el) => $(el).text())
    .join('\n');
  const ld = matchPrice(lds, /"price"\s*:\s*"?([\d.,]+)"?[^}]*?"priceCurrency"\s*:\s*"([A-Z]{3})"/i);
  if (ld) return ld;

  // schema.org itemprop
  const itemPrice = $('[itemprop="price"]').attr('content') || $('[itemprop="price"]').text();
  const itemCurr = $('[itemprop="priceCurrency"]').attr('content');
  if (itemPrice) {
    const v = parseAmount(itemPrice);
    if (v !== undefined) return { value: v, currency: (itemCurr || 'USD').toUpperCase() };
  }

  // OG price
  const ogAmt = $('meta[property="og:price:amount"], meta[property="product:price:amount"]').attr(
    'content',
  );
  const ogCur = $(
    'meta[property="og:price:currency"], meta[property="product:price:currency"]',
  ).attr('content');
  if (ogAmt) {
    const v = parseAmount(ogAmt);
    if (v !== undefined) return { value: v, currency: (ogCur || 'USD').toUpperCase() };
  }

  // Heuristic
  const body = $('body').text().slice(0, 10000);
  const m = /([€$£¥₽])\s?([\d]+[.,]?\d{0,2})|(USD|EUR|GBP|CNY|JPY|RUB)\s?([\d]+[.,]?\d{0,2})/.exec(
    body,
  );
  if (m) {
    const amt = parseAmount(m[2] ?? m[4] ?? '');
    if (amt !== undefined) {
      const sym = m[1] ?? m[3] ?? 'USD';
      return { value: amt, currency: symbolToIso(sym) };
    }
  }
  return undefined;
}

/** Pick a high-quality product thumbnail. */
export function extractThumbnail(
  $: cheerio.CheerioAPI,
  base: string,
): string | undefined {
  const og =
    $('meta[property="og:image:secure_url"]').attr('content') ||
    $('meta[property="og:image"]').attr('content') ||
    $('meta[name="twitter:image"]').attr('content');
  if (og) return absolutize(og, base);

  const imgs = $('img').toArray();
  let best: { url: string; score: number } | undefined;
  for (const el of imgs) {
    const src =
      $(el).attr('src') ||
      $(el).attr('data-src') ||
      $(el).attr('data-original') ||
      $(el).attr('srcset')?.split(',').pop()?.trim().split(' ')[0];
    if (!src) continue;
    const w = Number($(el).attr('width')) || 0;
    const h = Number($(el).attr('height')) || 0;
    const score = w * h || w + h;
    if (score < 200) continue;
    if (!best || score > best.score) best = { url: absolutize(src, base), score };
  }
  return best?.url;
}

/** Pick the most reliable title (og:title → h1 → <title>). */
export function extractTitle($: cheerio.CheerioAPI): string | undefined {
  const og = $('meta[property="og:title"]').attr('content')?.trim();
  if (og) return og;
  const h1 = $('h1').first().text().trim();
  if (h1) return h1;
  const t = $('title').text().trim();
  return t || undefined;
}

/**
 * Match "Ships in X-Y days" / "X day delivery" etc. Returns the LOWER bound
 * so buyers see the best-case shipping estimate in the summary.
 */
export function extractShippingDays($: cheerio.CheerioAPI): number | undefined {
  const body = $('body').text();
  const rx = /(\d{1,2})\s*(?:-|to|–)?\s*(\d{1,2})?\s*(?:days?|giorni|дн)/i;
  const m = rx.exec(body);
  if (!m) return undefined;
  const lo = Number(m[1]);
  return Number.isFinite(lo) && lo > 0 && lo < 120 ? lo : undefined;
}

export async function downloadThumb(
  requestId: string,
  supplier: string,
  thumbUrl: string,
  referer: string,
): Promise<string> {
  const tmp = path.join(os.tmpdir(), 'supplier-finder', 'thumbs');
  if (!existsSync(tmp)) await mkdir(tmp, { recursive: true });
  const out = path.join(tmp, `${requestId}.${supplier}.jpg`);
  const res = await axios.get<ArrayBuffer>(thumbUrl, {
    responseType: 'arraybuffer',
    timeout: 10000,
    maxRedirects: 5,
    headers: {
      'User-Agent': pickUserAgent(),
      Referer: referer,
      Accept: 'image/avif,image/webp,image/*,*/*;q=0.8',
    },
  });
  await writeFile(out, Buffer.from(res.data));
  return out;
}

/**
 * Validate a candidate listing against the reference.
 *
 * Hybrid scoring:
 *   - Visual (CLIP cosine, weight 0.7) when an embedding is available.
 *   - Textual (titleScore × 0.15 + keyword hit rate × 0.15) always applied.
 *
 * When CLIP is unavailable (offline / model-load failure), the text-only
 * half still produces a best-effort score clamped to a lower ceiling (60)
 * because we can't rule out a visually wrong match.
 */
export async function validateListing(opts: {
  requestId: string;
  supplier: string;
  listing: SupplierListing;
  referenceTitle?: string;
  referenceKeywords: readonly string[];
  referenceEmbedding?: Float32Array;
}): Promise<number> {
  const { listing, referenceEmbedding } = opts;
  const textScore = computeTextScore(opts);

  if (!referenceEmbedding) {
    // Text-only path: cap at 60 (must cross MIN_CONFIDENCE but never claim
    // high confidence without visual check).
    return Math.min(60, textScore);
  }

  if (!listing.thumbnail) {
    return Math.round(textScore * 0.7); // no image to check → discount text score
  }

  try {
    const thumbPath = await downloadThumb(
      opts.requestId,
      opts.supplier,
      listing.thumbnail,
      listing.url,
    );
    const cand = await embedImage(thumbPath);
    const visual = similarityScore(cand, referenceEmbedding);
    // 70% visual, 30% text
    return Math.round(visual * 0.7 + textScore * 0.3);
  } catch {
    return Math.round(textScore * 0.6);
  }
}

function computeTextScore(opts: {
  listing: SupplierListing;
  referenceTitle?: string;
  referenceKeywords: readonly string[];
}): number {
  const { listing, referenceTitle, referenceKeywords } = opts;
  const title = referenceTitle
    ? textTitleScore(referenceTitle, listing.title)
    : 0;
  const kwHit = keywordHitRate(referenceKeywords, listing.title);
  return Math.round(title * 0.5 + kwHit * 0.5);
}

function matchPrice(text: string, rx: RegExp): PriceLike | undefined {
  const m = rx.exec(text);
  if (!m) return undefined;
  const v = parseAmount(m[1]!);
  if (v === undefined) return undefined;
  return { value: v, currency: m[2]!.toUpperCase() };
}

function parseAmount(raw: string): number | undefined {
  const cleaned = raw.replace(/[^\d.,-]/g, '');
  if (!cleaned) return undefined;
  const lastDot = cleaned.lastIndexOf('.');
  const lastComma = cleaned.lastIndexOf(',');
  let normalized = cleaned;
  if (lastDot > -1 && lastComma > -1) {
    normalized = lastComma > lastDot ? cleaned.replace(/\./g, '').replace(',', '.') : cleaned.replace(/,/g, '');
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
    case '₽':
      return 'RUB';
    default:
      return sym.toUpperCase();
  }
}

function absolutize(src: string, base: string): string {
  try {
    return new URL(src, base).toString();
  } catch {
    return src;
  }
}
