/**
 * Supplier Finder — public library entry point.
 *
 * Each step plugs a new stage into the pipeline. Current wiring (Step 2):
 *   1. Input normalization: URL → Playwright + Cheerio scrape + image download,
 *      or raw image → Sharp preprocessing.
 *   2. OCR: Tesseract.js on the preprocessed JPEG → keywords.
 *   3–5. (pending) CLIP embedding, reverse image search, supplier crawlers.
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
import { preprocessImage } from './input/imageHandler.js';
import { extractFromUrl } from './input/urlExtractor.js';
import { runOcr, buildSearchKeywords } from './ocr/tesseractEngine.js';
import { embedImage } from './matching/clipSimilarity.js';
import { runVisualSearch } from './visualSearch/index.js';

export * from './types.js';
export { config } from './config.js';
export { logger };

export async function findSuppliers(input: FinderInput): Promise<FinderResult> {
  const requestId = randomUUID();
  const log = requestLogger(requestId);
  const started = Date.now();

  validateInput(input);
  const inputType = input.url ? 'url' : 'image';
  log.info({ inputType, suppliers: input.suppliers?.length ?? SUPPLIER_NAMES.length }, 'pipeline: start');

  const search = await buildSearchInput(requestId, input);

  log.info(
    {
      imagePath: search.imagePath,
      title: search.title,
      keywords: search.keywords,
      warnings: search.warnings,
    },
    'pipeline: input normalized',
  );

  // Step 4: discover candidate URLs via reverse-image-search across 3 engines.
  const visual = await runVisualSearch(search);
  log.info(
    {
      total: visual.all.length,
      supplierHits: Object.fromEntries(
        [...visual.bySupplier.entries()].map(([k, v]) => [k, v.length]),
      ),
    },
    'pipeline: visual search done',
  );

  // Steps 5–6 stop: supplier modules not yet wired — but we can at least
  // surface any URL that matched a supplier domain during visual search.
  const targets: SupplierName[] =
    input.suppliers && input.suppliers.length > 0 ? input.suppliers : [...SUPPLIER_NAMES];

  const results: SupplierResponse[] = targets.map((supplier): SupplierResponse => {
    const hits = visual.bySupplier.get(supplier) ?? [];
    if (hits.length === 0) {
      return {
        supplier,
        status: 'NOT_AVAILABLE',
        reason: 'no visual match — supplier crawler pending',
      };
    }
    const top = hits[0]!;
    // Confidence is a placeholder (engine-based rank only) until Step 5
    // plugs the CLIP validation on the candidate page's main image.
    return {
      supplier,
      status: 'FOUND',
      confidence: 60,
      productUrl: top.url,
      title: top.title ?? supplier,
      ...(top.thumbnail ? { thumbnail: top.thumbnail } : {}),
    };
  });

  const executionTimeMs = Date.now() - started;
  log.info({ executionTimeMs }, 'pipeline: done');

  return {
    query: {
      inputType: search.inputType,
      ...(search.originalUrl ? { originalSource: search.originalUrl } : {}),
      ...(search.title ? { extractedTitle: search.title } : {}),
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

/** Runs Step 1+2: turn FinderInput into a fully-populated SearchInput. */
export async function buildSearchInput(
  requestId: string,
  input: FinderInput,
): Promise<SearchInput> {
  const log = requestLogger(requestId);
  const warnings: string[] = [];
  let imagePath: string;
  let title: string | undefined;
  let originalUrl: string | undefined;
  let sourceImageUrl: string | undefined;

  if (input.url) {
    const ex = await extractFromUrl(requestId, input.url);
    imagePath = ex.imagePath;
    title = ex.title;
    originalUrl = ex.finalUrl;
    sourceImageUrl = ex.sourceImageUrl;
    warnings.push(...ex.warnings);
  } else {
    const pre = await preprocessImage({
      requestId,
      ...(input.imagePath ? { imagePath: input.imagePath } : {}),
      ...(input.imageBase64 ? { imageBase64: input.imageBase64 } : {}),
    });
    imagePath = pre.imagePath;
    warnings.push(...pre.warnings);
  }

  // OCR and CLIP embedding are independent — run them in parallel.
  const [ocr, embedding] = await Promise.all([
    runOcr(imagePath),
    embedImage(imagePath).catch((err) => {
      log.warn({ err: (err as Error).message }, 'clip embedding failed — visual matching disabled');
      warnings.push('clip embedding unavailable — will rely on text-based matching only');
      return undefined;
    }),
  ]);

  if (!ocr.text) warnings.push('ocr produced no text — relying on visual search only');
  const keywords = buildSearchKeywords(title, ocr.keywords);

  log.debug(
    {
      ocrChars: ocr.text.length,
      keywordCount: keywords.length,
      embeddingDim: embedding?.length ?? 0,
    },
    'input stage done',
  );

  return {
    requestId,
    inputType: input.url ? 'url' : 'image',
    imagePath,
    ...(originalUrl ? { originalUrl } : {}),
    ...(sourceImageUrl ? { sourceImageUrl } : {}),
    ...(title ? { title } : {}),
    keywords,
    ...(ocr.text ? { ocrText: ocr.text } : {}),
    ...(embedding ? { embedding } : {}),
    warnings,
  };
}

export { runVisualSearch } from './visualSearch/index.js';

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
