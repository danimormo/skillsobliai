import type { Page } from 'playwright';
import type { VisualCandidate } from '../types.js';

export interface RawAnchor {
  href: string;
  text?: string;
  thumb?: string;
}

/**
 * Pure normalizer: accepts raw anchor rows (href + optional text/thumb) and
 * produces the canonical `VisualCandidate[]`.
 *
 * Splitting this out keeps the DOM-dependent part tiny (a single `$$eval`)
 * while making filter logic unit-testable without a live browser.
 *
 * Filters applied:
 *   - Keep only http/https URLs
 *   - Drop search-engine internal links (google/yandex/bing/microsoft)
 *   - URL-exact dedupe, fragment stripped
 */
export function normalizeAnchors(
  rows: readonly RawAnchor[],
  source: VisualCandidate['source'],
): VisualCandidate[] {
  const seen = new Set<string>();
  const out: VisualCandidate[] = [];

  for (const r of rows) {
    let u: URL;
    try {
      u = new URL(r.href);
    } catch {
      continue;
    }
    if (u.protocol !== 'http:' && u.protocol !== 'https:') continue;
    const host = u.hostname.toLowerCase();
    if (/(^|\.)google\./.test(host)) continue;
    if (/(^|\.)yandex\./.test(host)) continue;
    if (/(^|\.)bing\./.test(host)) continue;
    if (/(^|\.)microsoft\./.test(host)) continue;

    u.hash = '';
    const key = u.toString();
    if (seen.has(key)) continue;
    seen.add(key);

    const trimmedText = r.text?.trim().slice(0, 200);

    out.push({
      url: key,
      source,
      domain: host,
      ...(trimmedText ? { title: trimmedText } : {}),
      ...(r.thumb ? { thumbnail: r.thumb } : {}),
    });
  }
  return out;
}

/**
 * DOM-side extractor. Queries every `<a href>` on the current page and pipes
 * the rows through `normalizeAnchors`. Kept deliberately selector-agnostic:
 * search engines shuffle CSS class names constantly, so DOM structure hunting
 * breaks within weeks. Anchor + hostname filter is the most resilient contract.
 */
export async function extractAnchors(
  page: Page,
  source: VisualCandidate['source'],
): Promise<VisualCandidate[]> {
  const rows = await page.$$eval('a[href]', (els) =>
    (els as HTMLAnchorElement[]).map((a) => ({
      href: a.href,
      text: (a.textContent ?? '').trim(),
      thumb:
        (a.querySelector('img') as HTMLImageElement | null)?.src ||
        (a.querySelector('img') as HTMLImageElement | null)?.getAttribute('data-src') ||
        undefined,
    })),
  );
  return normalizeAnchors(rows, source);
}
