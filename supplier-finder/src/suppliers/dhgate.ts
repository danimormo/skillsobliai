import { BaseSupplier } from './base.js';
import { fetchPdp, pickFirstSearchHref, validateListing } from './pdp.js';
import type { SearchInput, SupplierListing, SupplierName } from '../types.js';

/**
 * DHgate — USA-first B2B from China, friendlier to scraping than 1688/Taobao.
 *
 * PDP shape:  /product/{slug}/{digits}.html
 * Search:     /wholesale/search.do?searchkey={encoded}
 */
export class DHgateSupplier extends BaseSupplier {
  readonly name: SupplierName = 'DHgate';
  readonly domain = 'dhgate.com';
  private static readonly PDP_RX = /\/product\/[\w-]+\/\d+\.html/;

  async searchByImage(input: SearchInput): Promise<SupplierListing | null> {
    const hit = input.candidates?.find((c) => /(^|\.)dhgate\.com$/i.test(c.domain));
    return hit ? fetchPdp(hit.url) : null;
  }

  async searchByKeywords(input: SearchInput): Promise<SupplierListing | null> {
    if (input.keywords.length === 0) return null;
    const q = input.keywords.slice(0, 5).join(' ').trim();
    if (!q) return null;
    const searchUrl = `https://www.dhgate.com/wholesale/search.do?searchkey=${encodeURIComponent(q)}`;
    const pdp = await pickFirstSearchHref(searchUrl, DHgateSupplier.PDP_RX);
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
