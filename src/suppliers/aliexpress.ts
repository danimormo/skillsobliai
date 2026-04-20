import { BaseSupplier } from './base.js';
import { fetchPdp, pickFirstSearchHref, validateListing } from './pdp.js';
import type { SearchInput, SupplierListing, SupplierName } from '../types.js';

/**
 * AliExpress — the reference implementation. Every other supplier follows the
 * same four-method shape: name + domain + searchByImage + searchByKeywords +
 * validateMatch. Heavy lifting is in `pdp.ts`.
 *
 * Discovery path:
 *   1. Reuse a Step-4 candidate URL on aliexpress.* → fetch PDP directly.
 *   2. (Reserved) native image search — requires cookie+token handshake.
 *   3. Keyword search at /w/wholesale-{query}.html → first /item/\d+.html.
 */
export class AliExpressSupplier extends BaseSupplier {
  readonly name: SupplierName = 'AliExpress';
  readonly domain = 'aliexpress.com';
  private static readonly PDP_RX = /\/item\/\d+\.html/;

  async searchByImage(input: SearchInput): Promise<SupplierListing | null> {
    const hit = input.candidates?.find((c) => /(^|\.)aliexpress\.(com|us|ru)$/i.test(c.domain));
    return hit ? fetchPdp(hit.url) : null;
  }

  async searchByKeywords(input: SearchInput): Promise<SupplierListing | null> {
    if (input.keywords.length === 0) return null;
    const query = input.keywords.slice(0, 5).join(' ').trim().replace(/\s+/g, '-');
    if (!query) return null;
    const searchUrl = `https://www.aliexpress.com/w/wholesale-${encodeURIComponent(query)}.html`;
    const pdp = await pickFirstSearchHref(searchUrl, AliExpressSupplier.PDP_RX);
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
