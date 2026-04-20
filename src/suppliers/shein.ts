import { BaseSupplier } from './base.js';
import { fetchPdp, pickFirstSearchHref, validateListing } from './pdp.js';
import type { SearchInput, SupplierListing, SupplierName } from '../types.js';

/**
 * Shein — fashion-focused dropshipping source.
 *
 * PDP shape:  /...-p-{digits}.html (the slug varies wildly, the `-p-{id}`
 *             terminator is what we anchor on).
 * Search:     /pdsearch/{query}/ with slashes (NOT query-string).
 *
 * Shein proxies static HTML from many regional subdomains (us, uk, de, it,
 * eur, sheinside.com). matchSupplier already folds them all to the Shein
 * name; here we only need to accept any shein.* or sheinside.* host in the
 * candidate bucket.
 */
export class SheinSupplier extends BaseSupplier {
  readonly name: SupplierName = 'Shein';
  readonly domain = 'shein.com';
  private static readonly PDP_RX = /-p-\d+\.html/;

  async searchByImage(input: SearchInput): Promise<SupplierListing | null> {
    const hit = input.candidates?.find((c) =>
      /(^|\.)(shein\.com|sheinside\.com)$/i.test(c.domain),
    );
    return hit ? fetchPdp(hit.url) : null;
  }

  async searchByKeywords(input: SearchInput): Promise<SupplierListing | null> {
    if (input.keywords.length === 0) return null;
    const q = input.keywords.slice(0, 5).join(' ').trim();
    if (!q) return null;
    const searchUrl = `https://us.shein.com/pdsearch/${encodeURIComponent(q)}/`;
    const pdp = await pickFirstSearchHref(searchUrl, SheinSupplier.PDP_RX);
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
