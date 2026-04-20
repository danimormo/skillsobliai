import { BaseSupplier } from './base.js';
import { fetchPdp, pickFirstSearchHref, validateListing } from './pdp.js';
import type { SearchInput, SupplierListing, SupplierName } from '../types.js';

/**
 * Taobao / Tmall — Alibaba's consumer marketplaces.
 *
 * Taobao gates nearly every search page behind a login-required wall
 * (login.taobao.com) for unauthenticated IPs outside China. The module
 * still tries, and falls through to ERROR / blocked on the login redirect.
 * When a Step-4 candidate URL already exists the PDP itself is usually
 * readable even without login, so the image-search path has a better
 * success rate than the keyword path.
 *
 * PDP shapes:
 *   taobao:  item.taobao.com/item.htm?id={digits}
 *   tmall:   detail.tmall.com/item.htm?id={digits}
 */
export class TaobaoSupplier extends BaseSupplier {
  readonly name: SupplierName = 'Taobao';
  readonly domain = 'taobao.com';
  private static readonly PDP_RX = /\/item\.htm\?(?:.*&)?id=\d+/;

  async searchByImage(input: SearchInput): Promise<SupplierListing | null> {
    const hit = input.candidates?.find((c) =>
      /(^|\.)(taobao\.com|tmall\.com)$/i.test(c.domain),
    );
    return hit ? fetchPdp(hit.url, { acceptPartial: true }) : null;
  }

  async searchByKeywords(input: SearchInput): Promise<SupplierListing | null> {
    if (input.keywords.length === 0) return null;
    const q = input.keywords.slice(0, 5).join(' ').trim();
    if (!q) return null;
    const searchUrl = `https://s.taobao.com/search?q=${encodeURIComponent(q)}`;
    const pdp = await pickFirstSearchHref(searchUrl, TaobaoSupplier.PDP_RX);
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
