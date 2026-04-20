import { BaseSupplier } from './base.js';
import { fetchPdp, pickFirstSearchHref, validateListing } from './pdp.js';
import type { SearchInput, SupplierListing, SupplierName } from '../types.js';

/**
 * Spocket — US/EU dropshipping marketplace. Catalog behind a soft paywall:
 * the /search page is public but PDP details require a trial/paid account.
 *
 * Strategy:
 *   1. Reuse a Step-4 candidate URL if Google Lens surfaced one publicly.
 *   2. Keyword search /search?query=… then follow the first /products/…
 *      link; `acceptPartial: true` lets us read Spocket's OG tags on the
 *      login-walled PDP page (title + og:image are exposed pre-login).
 *
 * When Spocket serves a 401/404 pre-auth gate, the module returns null and
 * the base supplier surfaces NOT_AVAILABLE.
 */
export class SpocketSupplier extends BaseSupplier {
  readonly name: SupplierName = 'Spocket';
  readonly domain = 'spocket.co';
  private static readonly PDP_RX = /\/products?\/[\w-]+/;

  async searchByImage(input: SearchInput): Promise<SupplierListing | null> {
    const hit = input.candidates?.find((c) =>
      /(^|\.)(spocket\.co|spocketapp\.com)$/i.test(c.domain),
    );
    return hit ? fetchPdp(hit.url, { acceptPartial: true }) : null;
  }

  async searchByKeywords(input: SearchInput): Promise<SupplierListing | null> {
    if (input.keywords.length === 0) return null;
    const q = input.keywords.slice(0, 5).join(' ').trim();
    if (!q) return null;
    const searchUrl = `https://www.spocket.co/search?query=${encodeURIComponent(q)}`;
    const pdp = await pickFirstSearchHref(searchUrl, SpocketSupplier.PDP_RX);
    return pdp ? fetchPdp(pdp, { acceptPartial: true }) : null;
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
}
