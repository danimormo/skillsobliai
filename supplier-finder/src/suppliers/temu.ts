import { BaseSupplier } from './base.js';
import { fetchPdp, pickFirstSearchHref, validateListing } from './pdp.js';
import type { SearchInput, SupplierListing, SupplierName } from '../types.js';

/**
 * Temu (Pinduoduo's western sibling).
 *
 * Extremely fingerprint-sensitive: without stealth the /search_result.html
 * endpoint returns a 302 → /challenge page within 1s. The Playwright-extra
 * stealth plugin gets past this on most egress IPs; on blocked IPs the
 * supplier cleanly falls through to ERROR / blocked.
 *
 * PDP shape:  /-g-{digits}.html and /item/{digits}.html both observed
 * Search:     /search_result.html?search_key={encoded}
 */
export class TemuSupplier extends BaseSupplier {
  readonly name: SupplierName = 'Temu';
  readonly domain = 'temu.com';
  private static readonly PDP_RX = /(?:-g-|\/item\/)\d+\.html/;

  async searchByImage(input: SearchInput): Promise<SupplierListing | null> {
    const hit = input.candidates?.find((c) => /(^|\.)temu\.com$/i.test(c.domain));
    return hit ? fetchPdp(hit.url) : null;
  }

  async searchByKeywords(input: SearchInput): Promise<SupplierListing | null> {
    if (input.keywords.length === 0) return null;
    const q = input.keywords.slice(0, 5).join(' ').trim();
    if (!q) return null;
    const searchUrl = `https://www.temu.com/search_result.html?search_key=${encodeURIComponent(q)}`;
    const pdp = await pickFirstSearchHref(searchUrl, TemuSupplier.PDP_RX);
    return pdp ? fetchPdp(pdp) : null;
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
