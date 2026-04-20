import { newStealthContext, detectCaptcha, humanDelay } from '../utils/browser.js';
import { requestLogger } from '../utils/logger.js';
import { config } from '../config.js';
import type { SearchInput, VisualCandidate } from '../types.js';
import { extractAnchors } from './candidates.js';

/**
 * Reverse-image-search via Bing Visual Search.
 *
 * Public entry: `/images/searchbyimage?cbir=sbi&imgurl=…`. Like Yandex it
 * requires a public image URL — and unlike Google Lens, Bing's POST upload
 * flow is gated by a `cvid` / `form` token handshake that keeps changing.
 * When only a local image is available the orchestrator falls back to Google
 * Lens file upload; no need to fight Bing for the same candidates.
 */
export async function bingVisualSearch(input: SearchInput): Promise<VisualCandidate[]> {
  const log = requestLogger(input.requestId).child({ stage: 'bing' });
  if (!input.sourceImageUrl) {
    log.debug('skip: no public image url');
    return [];
  }

  const ctx = await newStealthContext({ locale: 'en-US' });
  const page = await ctx.newPage();
  const started = Date.now();

  try {
    const target = `https://www.bing.com/images/searchbyimage?cbir=sbi&imgurl=${encodeURIComponent(
      input.sourceImageUrl,
    )}`;
    await page.goto(target, {
      waitUntil: 'domcontentloaded',
      timeout: config.browserTimeoutMs,
    });

    await page
      .waitForSelector('a[href^="http"]', { timeout: 12000 })
      .catch(() => null);

    if (await detectCaptcha(page)) {
      log.warn({ elapsedMs: Date.now() - started }, 'bing: captcha wall');
      return [];
    }

    await humanDelay(400, 1000);
    const all = await extractAnchors(page, 'bing');
    log.info({ count: all.length, elapsedMs: Date.now() - started }, 'bing: candidates');
    return all;
  } catch (err) {
    log.warn({ err: (err as Error).message, elapsedMs: Date.now() - started }, 'bing: failed');
    return [];
  } finally {
    await ctx.close().catch(() => {});
  }
}
