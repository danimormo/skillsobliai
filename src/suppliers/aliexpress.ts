import * as cheerio from 'cheerio';
import { BaseSupplier } from './base.js';
import {
  extractPrice,
  extractShippingDays,
  extractThumbnail,
  extractTitle,
  validateListing,
} from './pdp.js';
import { newStealthContext, detectCaptcha, humanDelay } from '../utils/browser.js';
import type { SearchInput, SupplierListing, SupplierName } from '../types.js';

/**
 * AliExpress — the template other suppliers follow.
 *
 * Three discovery paths, tried in order:
 *   1. Step-4 candidate URL already pointing at aliexpress.com → just fetch
 *      and normalize the PDP.
 *   2. (Reserved) AliExpress native image search. The public endpoint at
 *      `sale.aliexpress.com/__pc/…` requires a session cookie handshake and
 *      an image upload to `mobile.aliexpress.com/api/v1/imageSearch`. Skipped
 *      until we have a stable harness — the Step-4 visual search covers 90%
 *      of the value anyway.
 *   3. Keyword search at `/w/wholesale-{query}.html` → first non-sponsored
 *      card.
 *
 * Anti-bot: AliExpress shows a slider CAPTCHA (nocaptcha.aliyun.com) for
 * suspicious fingerprints. We detect and fail fast (`ERROR / captcha`); we
 * do NOT try to solve it.
 */
export class AliExpressSupplier extends BaseSupplier {
  readonly name: SupplierName = 'AliExpress';
  readonly domain = 'aliexpress.com';

  async searchByImage(input: SearchInput): Promise<SupplierListing | null> {
    const hit = input.candidates?.find((c) =>
      /(^|\.)aliexpress\.(com|us|ru)$/i.test(c.domain),
    );
    if (!hit) return null;
    return this.fetchListing(hit.url);
  }

  async searchByKeywords(input: SearchInput): Promise<SupplierListing | null> {
    if (input.keywords.length === 0) return null;
    const query = input.keywords.slice(0, 5).join(' ').trim();
    if (!query) return null;
    const url = `https://www.aliexpress.com/w/wholesale-${encodeURIComponent(
      query.replace(/\s+/g, '-'),
    )}.html`;
    const firstItemUrl = await this.pickFirstSearchResult(url);
    if (!firstItemUrl) return null;
    return this.fetchListing(firstItemUrl);
  }

  async validateMatch(listing: SupplierListing, input: SearchInput): Promise<number> {
    return validateListing({
      requestId: input.requestId,
      supplier: this.name,
      listing,
      referenceKeywords: input.keywords,
      ...(input.title ? { referenceTitle: input.title } : {}),
      ...(input.embedding ? { referenceEmbedding: input.embedding } : {}),
    });
  }

  /** Navigate to an AliExpress PDP and normalize it into a SupplierListing. */
  private async fetchListing(url: string): Promise<SupplierListing | null> {
    const ctx = await newStealthContext();
    const page = await ctx.newPage();
    try {
      const res = await page.goto(url, { waitUntil: 'domcontentloaded' });
      if (!res || res.status() >= 400) return null;

      await page.waitForLoadState('networkidle', { timeout: 4000 }).catch(() => null);

      if (await detectCaptcha(page)) throw new Error('aliexpress captcha detected');

      await humanDelay(400, 900);
      const html = await page.content();
      const finalUrl = page.url();
      const $ = cheerio.load(html);

      const title =
        extractTitle($) ||
        $('h1[data-pl="product-title"], h1.product-title, h1.title').first().text().trim();
      if (!title) return null;

      const price = extractPrice(html, $);
      const thumbnail = extractThumbnail($, finalUrl);
      const shippingDays = extractShippingDays($);

      const listing: SupplierListing = {
        url: finalUrl,
        title,
        ...(price ? { price } : {}),
        ...(thumbnail ? { thumbnail } : {}),
        ...(shippingDays ? { estimatedShippingDays: shippingDays } : {}),
      };
      return listing;
    } finally {
      await ctx.close().catch(() => {});
    }
  }

  /** Pick the first organic product card from an AliExpress search page. */
  private async pickFirstSearchResult(searchUrl: string): Promise<string | undefined> {
    const ctx = await newStealthContext();
    const page = await ctx.newPage();
    try {
      const res = await page.goto(searchUrl, { waitUntil: 'domcontentloaded' });
      if (!res || res.status() >= 400) return undefined;
      await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => null);
      if (await detectCaptcha(page)) throw new Error('aliexpress captcha on search');

      // Resilient selector: AliExpress uses many variants over time, but every
      // organic PDP link looks like `/item/{digits}.html`.
      const hrefs = await page.$$eval(
        'a[href*="/item/"]',
        (els) =>
          (els as HTMLAnchorElement[])
            .map((a) => a.href)
            .filter((h) => /\/item\/\d+\.html/.test(h)),
      );
      const unique = [...new Set(hrefs)];
      return unique[0];
    } finally {
      await ctx.close().catch(() => {});
    }
  }
}
