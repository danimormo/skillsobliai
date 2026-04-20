import { BaseSupplier } from './base.js';
import { fetchPdp, pickFirstSearchHref, validateListing } from './pdp.js';
import type { SearchInput, SupplierListing, SupplierName } from '../types.js';

/**
 * CJDropshipping — the most dropshipper-friendly marketplace in the stack.
 *
 * PDP shape:  /product/{slug}-{digits}.html
 * Search:     /list/search/{encoded}.html
 *
 * Catalog is fully scrapeable without login; the main failure mode is the
 * inventory "no results" state which `pickFirstSearchHref` treats as
 * "supplier didn't stock this item" (NOT_AVAILABLE).
 */
export class CJDropshippingSupplier extends BaseSupplier {
  readonly name: SupplierName = 'CJDropshipping';
  readonly domain = 'cjdropshipping.com';
  private static readonly PDP_RX = /\/product\/[\w-]+-\d+\.html/;

  async searchByImage(input: SearchInput): Promise<SupplierListing | null> {
    const hit = input.candidates?.find((c) =>
      /(^|\.)cjdropshipping\.(com|cn)$/i.test(c.domain),
    );
    return hit ? fetchPdp(hit.url) : null;
  }

  async searchByKeywords(input: SearchInput): Promise<SupplierListing | null> {
    if (input.keywords.length === 0) return null;
    const q = input.keywords.slice(0, 5).join(' ').trim();
    if (!q) return null;
    const searchUrl = `https://cjdropshipping.com/list/search/${encodeURIComponent(q)}.html`;
    const pdp = await pickFirstSearchHref(searchUrl, CJDropshippingSupplier.PDP_RX);
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
