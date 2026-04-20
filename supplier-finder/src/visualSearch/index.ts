import type { SearchInput, SupplierName, VisualCandidate } from '../types.js';
import { googleLensSearch } from './googleLens.js';
import { yandexImageSearch } from './yandexImages.js';
import { bingVisualSearch } from './bingVisual.js';
import { matchSupplier } from './domains.js';
import { requestLogger } from '../utils/logger.js';

export { matchSupplier, isSupplierDomain, SUPPLIER_DOMAINS } from './domains.js';
export { extractAnchors, normalizeAnchors } from './candidates.js';

export interface VisualSearchOutcome {
  all: VisualCandidate[];
  bySupplier: Map<SupplierName, VisualCandidate[]>;
  /** Raw count per engine for observability. */
  engines: { google: number; yandex: number; bing: number };
}

/**
 * Run all three reverse-image engines in parallel (Promise.allSettled so one
 * failure never cascades) and bucket the candidates by matched supplier.
 *
 * Dedupe is URL-exact, and within each supplier bucket candidates are sorted
 * to prefer Google Lens (best coverage for western marketplaces) over Yandex
 * (best coverage for Asian ones) over Bing (fallback).
 */
export async function runVisualSearch(input: SearchInput): Promise<VisualSearchOutcome> {
  const log = requestLogger(input.requestId).child({ stage: 'visualSearch' });
  const started = Date.now();

  const [g, y, b] = await Promise.allSettled([
    googleLensSearch(input),
    yandexImageSearch(input),
    bingVisualSearch(input),
  ]);

  const google = g.status === 'fulfilled' ? g.value : [];
  const yandex = y.status === 'fulfilled' ? y.value : [];
  const bing = b.status === 'fulfilled' ? b.value : [];

  // URL-exact dedupe preserving the first engine that surfaced the hit.
  const seen = new Set<string>();
  const all: VisualCandidate[] = [];
  for (const c of [...google, ...yandex, ...bing]) {
    if (seen.has(c.url)) continue;
    seen.add(c.url);
    all.push(c);
  }

  const bySupplier = new Map<SupplierName, VisualCandidate[]>();
  for (const c of all) {
    const name = matchSupplier(c.domain);
    if (!name) continue;
    const arr = bySupplier.get(name) ?? [];
    arr.push(c);
    bySupplier.set(name, arr);
  }

  log.info(
    {
      total: all.length,
      google: google.length,
      yandex: yandex.length,
      bing: bing.length,
      supplierHits: Object.fromEntries(
        [...bySupplier.entries()].map(([k, v]) => [k, v.length]),
      ),
      elapsedMs: Date.now() - started,
    },
    'visual search complete',
  );

  return {
    all,
    bySupplier,
    engines: { google: google.length, yandex: yandex.length, bing: bing.length },
  };
}
