import { newStealthContext, detectCaptcha, humanDelay } from '../utils/browser.js';
import { requestLogger } from '../utils/logger.js';
import { config } from '../config.js';
import { getDomainLimiter } from '../utils/rateLimiter.js';
import type { SearchInput, VisualCandidate } from '../types.js';
import { extractAnchors } from './candidates.js';

const RESULTS_SELECTOR = 'a[href^="http"]';
const PAGE_READY_TIMEOUT = 15000;

/**
 * Reverse-image-search via Google Lens.
 *
 * Two entry modes:
 *   - `sourceImageUrl` known  → `lens.google.com/uploadbyurl?url=…` (no file I/O)
 *   - local image only        → navigate to `lens.google.com/` and drive the
 *                               hidden `<input type="file">` programmatically
 *
 * Never throws. On CAPTCHA, timeout, or navigation error it logs a warning and
 * returns `[]` so the outer orchestrator can still fall back to Yandex/Bing.
 */
export async function googleLensSearch(input: SearchInput): Promise<VisualCandidate[]> {
  const log = requestLogger(input.requestId).child({ stage: 'googleLens' });
  const limiter = getDomainLimiter('lens.google.com');
  return limiter.schedule({ expiration: config.supplierTimeoutMs }, () =>
    runGoogleLensSearch(input, log),
  );
}

async function runGoogleLensSearch(
  input: SearchInput,
  log: ReturnType<typeof requestLogger>,
): Promise<VisualCandidate[]> {
  const ctx = await newStealthContext();
  const page = await ctx.newPage();
  const started = Date.now();

  try {
    if (input.sourceImageUrl) {
      const target = `https://lens.google.com/uploadbyurl?url=${encodeURIComponent(input.sourceImageUrl)}`;
      await page.goto(target, {
        waitUntil: 'domcontentloaded',
        timeout: config.browserTimeoutMs,
      });
    } else {
      await page.goto('https://lens.google.com/', {
        waitUntil: 'domcontentloaded',
        timeout: config.browserTimeoutMs,
      });
      const fileInput = await page.waitForSelector('input[type="file"]', { timeout: 10000 });
      await fileInput.setInputFiles(input.imagePath);
    }

    await page
      .waitForSelector(RESULTS_SELECTOR, { timeout: PAGE_READY_TIMEOUT })
      .catch(() => null);

    if (await detectCaptcha(page)) {
      log.warn({ elapsedMs: Date.now() - started }, 'google lens: captcha wall');
      return [];
    }

    await humanDelay(800, 1500);
    // Let the SPA hydrate additional tiles.
    await page
      .waitForLoadState('networkidle', { timeout: 5000 })
      .catch(() => null);

    const all = await extractAnchors(page, 'google-lens');
    log.info({ count: all.length, elapsedMs: Date.now() - started }, 'google lens: candidates');
    return all;
  } catch (err) {
    log.warn(
      { err: (err as Error).message, elapsedMs: Date.now() - started },
      'google lens: failed',
    );
    return [];
  } finally {
    await ctx.close().catch(() => {});
  }
}
