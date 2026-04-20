import { newStealthContext, detectCaptcha, humanDelay } from '../utils/browser.js';
import { requestLogger } from '../utils/logger.js';
import { config } from '../config.js';
import type { SearchInput, VisualCandidate } from '../types.js';
import { extractAnchors } from './candidates.js';

/**
 * Reverse-image-search via Yandex Images — strongest of the three on Asian
 * / Chinese marketplace matches (Taobao, 1688, DHgate).
 *
 * Only works with a public image URL. Yandex's web upload flow requires a
 * multi-step multipart POST to `/images-apphost/cbir-upload` plus anti-bot
 * tokens refreshed every few hours; skipping it keeps the module resilient.
 * When input is a raw user upload the orchestrator simply returns `[]`.
 */
export async function yandexImageSearch(input: SearchInput): Promise<VisualCandidate[]> {
  const log = requestLogger(input.requestId).child({ stage: 'yandex' });
  if (!input.sourceImageUrl) {
    log.debug('skip: no public image url');
    return [];
  }

  const ctx = await newStealthContext({ locale: 'en-US' });
  const page = await ctx.newPage();
  const started = Date.now();

  try {
    const target = `https://yandex.com/images/search?rpt=imageview&url=${encodeURIComponent(
      input.sourceImageUrl,
    )}`;
    await page.goto(target, {
      waitUntil: 'domcontentloaded',
      timeout: config.browserTimeoutMs,
    });

    await page
      .waitForSelector('a.CbirSites-ItemTitle, a.Link.CbirItem-Title, a[href^="http"]', {
        timeout: 12000,
      })
      .catch(() => null);

    if (await detectCaptcha(page)) {
      log.warn({ elapsedMs: Date.now() - started }, 'yandex: captcha wall');
      return [];
    }

    await humanDelay(500, 1200);
    const all = await extractAnchors(page, 'yandex');
    log.info({ count: all.length, elapsedMs: Date.now() - started }, 'yandex: candidates');
    return all;
  } catch (err) {
    log.warn({ err: (err as Error).message, elapsedMs: Date.now() - started }, 'yandex: failed');
    return [];
  } finally {
    await ctx.close().catch(() => {});
  }
}
