import type {
  SearchInput,
  SupplierListing,
  SupplierName,
  SupplierResponse,
  ErrorReason,
} from '../types.js';
import { requestLogger } from '../utils/logger.js';
import { getDomainLimiter } from '../utils/rateLimiter.js';
import { config } from '../config.js';

/**
 * Abstract base class for every supplier integration.
 *
 * Subclasses MUST implement `searchByImage`, `searchByKeywords`, and `validateMatch`.
 * The orchestration (image-first → keyword fallback → CLIP validation → error handling)
 * is centralized in `find()` so individual suppliers stay small and focused.
 *
 * Guarantee: `find()` NEVER throws. Failures are converted to `{status:'ERROR', ...}`.
 */
export abstract class BaseSupplier {
  abstract readonly name: SupplierName;
  /** Host used for domain-scoped rate limiting. e.g. "aliexpress.com". */
  abstract readonly domain: string;

  /** Try native image-search on the supplier's own site, if supported. */
  abstract searchByImage(input: SearchInput): Promise<SupplierListing | null>;

  /** Text-based search as fallback. */
  abstract searchByKeywords(input: SearchInput): Promise<SupplierListing | null>;

  /**
   * Given a candidate listing and the full reference SearchInput, return
   * confidence 0-100 of a visual + textual match.
   */
  abstract validateMatch(listing: SupplierListing, input: SearchInput): Promise<number>;

  async find(input: SearchInput): Promise<SupplierResponse> {
    const log = requestLogger(input.requestId).child({ supplier: this.name });
    const limiter = getDomainLimiter(this.domain);
    const start = Date.now();

    try {
      const result = await limiter.schedule(
        { expiration: config.supplierTimeoutMs },
        async () => {
          const fromImage = await this.safe(() => this.searchByImage(input), log, 'searchByImage');
          const listing =
            fromImage ??
            (await this.safe(() => this.searchByKeywords(input), log, 'searchByKeywords'));
          if (!listing) return null;

          const confidence = await this.safe(
            () => this.validateMatch(listing, input),
            log,
            'validateMatch',
          );

          return { listing, confidence: confidence ?? 0 };
        },
      );

      const elapsedMs = Date.now() - start;

      if (!result) {
        log.info({ elapsedMs }, 'supplier: no match');
        return { supplier: this.name, status: 'NOT_AVAILABLE' };
      }

      const { listing, confidence } = result;
      if (confidence < config.minConfidence) {
        log.info({ confidence, elapsedMs }, 'supplier: below confidence threshold');
        return {
          supplier: this.name,
          status: 'NOT_AVAILABLE',
          reason: `confidence ${confidence} < ${config.minConfidence}`,
        };
      }

      log.info({ confidence, url: listing.url, elapsedMs }, 'supplier: FOUND');
      return {
        supplier: this.name,
        status: 'FOUND',
        confidence,
        productUrl: listing.url,
        title: listing.title,
        ...(listing.price ? { price: listing.price } : {}),
        ...(listing.thumbnail ? { thumbnail: listing.thumbnail } : {}),
        ...(listing.estimatedShippingDays
          ? { estimatedShippingDays: listing.estimatedShippingDays }
          : {}),
      };
    } catch (err) {
      const elapsedMs = Date.now() - start;
      const { message, reason } = classifyError(err);
      log.warn({ err: message, reason, elapsedMs }, 'supplier: ERROR');
      return { supplier: this.name, status: 'ERROR', error: message, reason };
    }
  }

  private async safe<T>(
    fn: () => Promise<T>,
    log: ReturnType<typeof requestLogger>,
    step: string,
  ): Promise<T | null> {
    try {
      return await fn();
    } catch (err) {
      const { message } = classifyError(err);
      log.debug({ step, err: message }, 'supplier sub-step failed');
      return null;
    }
  }
}

export function classifyError(err: unknown): { message: string; reason: ErrorReason } {
  const message = err instanceof Error ? err.message : String(err);
  const lower = message.toLowerCase();
  if (lower.includes('captcha') || lower.includes('recaptcha')) {
    return { message, reason: 'captcha' };
  }
  if (lower.includes('timeout') || lower.includes('timed out')) {
    return { message, reason: 'timeout' };
  }
  if (lower.includes('403') || lower.includes('blocked') || lower.includes('forbidden')) {
    return { message, reason: 'blocked' };
  }
  if (lower.includes('enotfound') || lower.includes('econnreset') || lower.includes('network')) {
    return { message, reason: 'network' };
  }
  if (lower.includes('parse') || lower.includes('selector')) {
    return { message, reason: 'parse' };
  }
  return { message, reason: 'unknown' };
}
