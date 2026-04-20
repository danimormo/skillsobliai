/**
 * Core types shared across the Supplier Finder pipeline.
 *
 * Conventions:
 * - All prices are kept as numeric values + ISO currency code; never as formatted strings.
 * - Embeddings are Float32Array (CLIP ViT-B/32 → 512 dims by default).
 * - Every supplier always returns a `SupplierResponse`, never throws.
 */

export type InputType = 'url' | 'image';

export type SupplierName =
  | 'AliExpress'
  | 'Alibaba'
  | '1688'
  | 'Temu'
  | 'Shein'
  | 'Taobao'
  | 'DHgate'
  | 'CJDropshipping'
  | 'Spocket';

export const SUPPLIER_NAMES: readonly SupplierName[] = [
  'AliExpress',
  'Alibaba',
  '1688',
  'Temu',
  'Shein',
  'Taobao',
  'DHgate',
  'CJDropshipping',
  'Spocket',
] as const;

export type SupplierStatus = 'FOUND' | 'NOT_AVAILABLE' | 'ERROR';

export interface Price {
  value: number;
  currency: string; // ISO-4217 (USD, EUR, CNY, …)
}

/** Canonical, normalized user input after Step 1. */
export interface SearchInput {
  requestId: string;
  inputType: InputType;
  /** Absolute path of the local preprocessed image (always present after Step 1). */
  imagePath: string;
  /** Source URL when inputType === 'url'. */
  originalUrl?: string;
  /** Extracted product title (from og:title / <h1> / Google Lens "best guess"). */
  title?: string;
  /** Ranked keywords for text-based supplier search. */
  keywords: string[];
  /** OCR output (brand names, labels on the product). */
  ocrText?: string;
  /** CLIP embedding (512-dim Float32Array) of the reference image. */
  embedding?: Float32Array;
  /** Warnings accumulated during preprocessing (e.g. "low-res image"). */
  warnings: string[];
}

/** A single candidate URL discovered via reverse-image-search. */
export interface VisualCandidate {
  url: string;
  source: 'google-lens' | 'yandex' | 'bing';
  thumbnail?: string;
  title?: string;
  /** Domain host extracted from URL, lower-cased. */
  domain: string;
}

/** Raw listing info extracted from a supplier page, pre-validation. */
export interface SupplierListing {
  url: string;
  title: string;
  thumbnail?: string;
  price?: Price;
  /** Supplier-reported shipping estimate (days), if parseable. */
  estimatedShippingDays?: number;
}

/** Full per-supplier response item in the final payload. */
export type SupplierResponse =
  | {
      supplier: SupplierName;
      status: 'FOUND';
      confidence: number; // 0-100
      productUrl: string;
      title: string;
      price?: Price;
      thumbnail?: string;
      estimatedShippingDays?: number;
    }
  | {
      supplier: SupplierName;
      status: 'NOT_AVAILABLE';
      reason?: string;
    }
  | {
      supplier: SupplierName;
      status: 'ERROR';
      error: string;
      /** Short machine-readable tag: 'captcha' | 'timeout' | 'blocked' | 'parse' | 'unknown'. */
      reason?: ErrorReason;
    };

export type ErrorReason =
  | 'captcha'
  | 'timeout'
  | 'blocked'
  | 'parse'
  | 'network'
  | 'unknown';

/** Full pipeline output returned to the caller. */
export interface FinderResult {
  query: {
    inputType: InputType;
    originalSource?: string;
    extractedTitle?: string;
    extractedKeywords: string[];
    timestamp: string; // ISO-8601
    requestId: string;
    warnings: string[];
  };
  results: SupplierResponse[];
  executionTimeMs: number;
  cacheHit: boolean;
}

/** Public entry-point input. Exactly one of `url` or `imageBase64`/`imagePath` must be set. */
export interface FinderInput {
  url?: string;
  imageBase64?: string;
  imagePath?: string;
  /** Optional override — limit search to these suppliers only. */
  suppliers?: SupplierName[];
  /** Skip Redis cache for this run. */
  noCache?: boolean;
}

export class PipelineError extends Error {
  constructor(
    message: string,
    public readonly reason: ErrorReason = 'unknown',
  ) {
    super(message);
    this.name = 'PipelineError';
  }
}
