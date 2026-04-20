/**
 * Supplier Finder — public library entry point.
 *
 * The orchestrator here is intentionally minimal in Step 1: it normalizes
 * input, returns `NOT_AVAILABLE` for every supplier, and records timing.
 * Each subsequent step wires in a real stage (OCR → CLIP → reverse-search →
 * per-supplier crawlers → cache).
 */
import { randomUUID } from 'node:crypto';
import type {
  FinderInput,
  FinderResult,
  SearchInput,
  SupplierName,
  SupplierResponse,
} from './types.js';
import { SUPPLIER_NAMES, PipelineError } from './types.js';
import { logger, requestLogger } from './utils/logger.js';

export * from './types.js';
export { config } from './config.js';
export { logger };

/** Placeholder: later steps replace this with a real orchestration. */
export async function findSuppliers(input: FinderInput): Promise<FinderResult> {
  const requestId = randomUUID();
  const log = requestLogger(requestId);
  const started = Date.now();

  validateInput(input);

  log.info(
    {
      hasUrl: !!input.url,
      hasImage: !!(input.imageBase64 || input.imagePath),
      suppliers: input.suppliers?.length ?? SUPPLIER_NAMES.length,
    },
    'pipeline: start',
  );

  // Step 1 stub: no preprocessing yet; all suppliers return NOT_AVAILABLE.
  const search: SearchInput = {
    requestId,
    inputType: input.url ? 'url' : 'image',
    imagePath: '',
    ...(input.url ? { originalUrl: input.url } : {}),
    keywords: [],
    warnings: ['pipeline running in Step-1 skeleton mode'],
  };

  const targets: SupplierName[] =
    input.suppliers && input.suppliers.length > 0 ? input.suppliers : [...SUPPLIER_NAMES];

  const results: SupplierResponse[] = targets.map((supplier) => ({
    supplier,
    status: 'NOT_AVAILABLE',
    reason: 'pipeline not yet implemented',
  }));

  const executionTimeMs = Date.now() - started;
  log.info({ executionTimeMs, resultCount: results.length }, 'pipeline: done');

  return {
    query: {
      inputType: search.inputType,
      ...(input.url ? { originalSource: input.url } : {}),
      extractedKeywords: search.keywords,
      timestamp: new Date().toISOString(),
      requestId,
      warnings: search.warnings,
    },
    results,
    executionTimeMs,
    cacheHit: false,
  };
}

function validateInput(input: FinderInput): void {
  const sources = [input.url, input.imageBase64, input.imagePath].filter(Boolean);
  if (sources.length === 0) {
    throw new PipelineError(
      'At least one of { url, imageBase64, imagePath } must be provided.',
      'parse',
    );
  }
  if (sources.length > 1) {
    throw new PipelineError('Provide exactly one input source (url, imageBase64, or imagePath).', 'parse');
  }
  if (input.url && !/^https?:\/\//i.test(input.url)) {
    throw new PipelineError('`url` must be an http(s) URL.', 'parse');
  }
}
