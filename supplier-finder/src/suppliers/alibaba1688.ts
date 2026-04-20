import { BaseSupplier } from './base.js';
import { fetchPdp, pickFirstSearchHref, validateListing } from './pdp.js';
import type { SearchInput, SupplierListing, SupplierName } from '../types.js';

/**
 * 1688.com — Alibaba's Chinese domestic sibling. Cheapest prices in the stack
 * but most aggressive anti-bot: expects a Chinese IP + cookie set on cold
 * visits. We still try; when it fails the BaseSupplier wraps the error and
 * the rest of the pipeline is unaffected. README documents the proxy
 * workaround (set PROXY_URL to a CN residential exit).
 *
 * PDP shape:  detail.1688.com/offer/{digits}.html
 * Search:     s.1688.com/selloffer/offer_search.htm?keywords={encoded}
 */
export class Alibaba1688Supplier extends BaseSupplier {
  readonly name: SupplierName = '1688';
  readonly domain = '1688.com';
  private static readonly PDP_RX = /\/offer\/\d+\.html/;

  async searchByImage(input: SearchInput): Promise<SupplierListing | null> {
    const hit = input.candidates?.find((c) => /(^|\.)1688\.com$/i.test(c.domain));
    return hit ? fetchPdp(hit.url) : null;
  }

  async searchByKeywords(input: SearchInput): Promise<SupplierListing | null> {
    if (input.keywords.length === 0) return null;
    const q = input.keywords.slice(0, 5).join(' ').trim();
    if (!q) return null;
    // 1688 expects keywords in URL-encoded GBK for Chinese chars; Node's
    // default UTF-8 encodeURIComponent works for Latin queries too.
    const searchUrl = `https://s.1688.com/selloffer/offer_search.htm?keywords=${encodeURIComponent(q)}`;
    const pdp = await pickFirstSearchHref(searchUrl, Alibaba1688Supplier.PDP_RX);
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
