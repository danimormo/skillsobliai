import { BaseSupplier } from './base.js';
import { fetchPdp, pickFirstSearchHref, validateListing } from './pdp.js';
import type { SearchInput, SupplierListing, SupplierName } from '../types.js';

/**
 * Alibaba (B2B parent of AliExpress).
 *
 * PDP shape:  /product-detail/{slug}_{digits}.html
 * Search:     /trade/search?SearchText={q}
 *
 * Anti-bot: Alibaba is milder than 1688/Taobao — it rarely throws a
 * slider CAPTCHA on product pages, but the search page is geo-aware and
 * can return a Chinese-only variant for some egress IPs. The stealth
 * context enforces en-US locale to keep selectors stable.
 */
export class AlibabaSupplier extends BaseSupplier {
  readonly name: SupplierName = 'Alibaba';
  readonly domain = 'alibaba.com';
  private static readonly PDP_RX = /\/product-detail\/[\w-]+_\d+\.html/;

  async searchByImage(input: SearchInput): Promise<SupplierListing | null> {
    const hit = input.candidates?.find((c) => /(^|\.)alibaba\.com$/i.test(c.domain));
    return hit ? fetchPdp(hit.url) : null;
  }

  async searchByKeywords(input: SearchInput): Promise<SupplierListing | null> {
    if (input.keywords.length === 0) return null;
    const q = input.keywords.slice(0, 5).join(' ').trim();
    if (!q) return null;
    const searchUrl = `https://www.alibaba.com/trade/search?SearchText=${encodeURIComponent(q)}`;
    const pdp = await pickFirstSearchHref(searchUrl, AlibabaSupplier.PDP_RX);
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
