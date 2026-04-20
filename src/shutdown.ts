import { closeBrowser } from './utils/browser.js';
import { closeCache } from './utils/cache.js';
import { shutdownLimiters } from './utils/rateLimiter.js';
import { shutdownOcr } from './ocr/tesseractEngine.js';
import { logger } from './utils/logger.js';

/**
 * Graceful teardown for long-running hosts (Express, CLI watchers). Idempotent
 * — safe to call multiple times. Each leg is awaited independently so one
 * stuck resource can't block the others.
 */
export async function shutdownPipeline(): Promise<void> {
  logger.debug('shutting down pipeline resources');
  await Promise.allSettled([closeBrowser(), closeCache(), shutdownLimiters(), shutdownOcr()]);
}
