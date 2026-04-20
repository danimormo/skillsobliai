import { mkdir, writeFile, stat } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import sharp from 'sharp';
import { logger } from '../utils/logger.js';

export interface PreprocessOutput {
  /** Absolute path to the preprocessed JPEG. */
  imagePath: string;
  /** Dimensions AFTER preprocessing. */
  width: number;
  height: number;
  /** Dimensions BEFORE preprocessing (may equal post). */
  originalWidth: number;
  originalHeight: number;
  /** Warnings (e.g. low-res source). */
  warnings: string[];
}

const MAX_DIM = 1024;
const LOW_RES_THRESHOLD = 300;
const TMP_ROOT = path.join(os.tmpdir(), 'supplier-finder');

async function ensureTmp(): Promise<string> {
  if (!existsSync(TMP_ROOT)) await mkdir(TMP_ROOT, { recursive: true });
  return TMP_ROOT;
}

export interface PreprocessInput {
  requestId: string;
  buffer?: Buffer;
  imagePath?: string;
  imageBase64?: string;
}

/**
 * Normalize any user-supplied image into a local JPEG:
 *   1. Load source (base64 / file path / raw buffer)
 *   2. Resize so max(w,h) ≤ 1024 (preserve aspect ratio, no upscale)
 *   3. Normalize (stretch histogram → better OCR / CLIP stability)
 *   4. Strip EXIF (privacy + smaller payload)
 *   5. Encode to JPEG q=88 and write to temp
 *
 * Emits warnings when the source is below 300×300 px. Never throws on
 * metadata parsing — it falls back to sharp output dimensions.
 */
export async function preprocessImage(input: PreprocessInput): Promise<PreprocessOutput> {
  const tmp = await ensureTmp();
  const source = await loadBuffer(input);

  const img = sharp(source, { failOn: 'none' }).rotate(); // auto-orient from EXIF then strip
  const meta = await img.metadata();
  const originalWidth = meta.width ?? 0;
  const originalHeight = meta.height ?? 0;

  const warnings: string[] = [];
  if (
    originalWidth > 0 &&
    originalHeight > 0 &&
    (originalWidth < LOW_RES_THRESHOLD || originalHeight < LOW_RES_THRESHOLD)
  ) {
    warnings.push(
      `low-resolution source image (${originalWidth}×${originalHeight} px, <${LOW_RES_THRESHOLD})`,
    );
  }

  const outPath = path.join(tmp, `${input.requestId}.jpg`);
  const processed = await img
    .resize({ width: MAX_DIM, height: MAX_DIM, fit: 'inside', withoutEnlargement: true })
    .normalise()
    .jpeg({ quality: 88, mozjpeg: true })
    .withMetadata({}) // drops EXIF
    .toFile(outPath);

  logger.debug(
    {
      originalWidth,
      originalHeight,
      width: processed.width,
      height: processed.height,
      outPath,
    },
    'image preprocessed',
  );

  return {
    imagePath: outPath,
    width: processed.width,
    height: processed.height,
    originalWidth: originalWidth || processed.width,
    originalHeight: originalHeight || processed.height,
    warnings,
  };
}

/**
 * Returns a centered-crop copy of `imagePath` keeping the central 70% of pixels.
 * Useful to strip watermarks / borders before running CLIP in ambiguous cases.
 */
export async function centerCrop(imagePath: string, ratio = 0.7): Promise<string> {
  const img = sharp(imagePath);
  const meta = await img.metadata();
  const w = meta.width ?? 0;
  const h = meta.height ?? 0;
  if (!w || !h) return imagePath;
  const cw = Math.floor(w * ratio);
  const ch = Math.floor(h * ratio);
  const left = Math.floor((w - cw) / 2);
  const top = Math.floor((h - ch) / 2);
  const out = imagePath.replace(/\.jpg$/i, '.crop.jpg');
  await img.extract({ left, top, width: cw, height: ch }).jpeg({ quality: 88 }).toFile(out);
  return out;
}

async function loadBuffer(input: PreprocessInput): Promise<Buffer> {
  if (input.buffer) return input.buffer;
  if (input.imageBase64) {
    const b64 = input.imageBase64.replace(/^data:image\/[a-z]+;base64,/, '');
    const buf = Buffer.from(b64, 'base64');
    if (buf.length === 0) throw new Error('imageBase64 decoded to empty buffer');
    if (buf.length > 10 * 1024 * 1024) throw new Error('image exceeds 10MB limit');
    return buf;
  }
  if (input.imagePath) {
    const info = await stat(input.imagePath);
    if (info.size > 10 * 1024 * 1024) throw new Error('image exceeds 10MB limit');
    const { readFile } = await import('node:fs/promises');
    return readFile(input.imagePath);
  }
  throw new Error('preprocessImage requires one of: buffer | imagePath | imageBase64');
}

/** Thin helper used by URL extractor to persist a downloaded image buffer. */
export async function saveTempImage(requestId: string, buffer: Buffer, ext = 'jpg'): Promise<string> {
  const tmp = await ensureTmp();
  const out = path.join(tmp, `${requestId}.raw.${ext}`);
  await writeFile(out, buffer);
  return out;
}
