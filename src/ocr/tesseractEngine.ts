import { createWorker, type Worker } from 'tesseract.js';
import { logger } from '../utils/logger.js';

export interface OcrResult {
  text: string;
  keywords: string[];
  /** Tesseract mean confidence 0-100 on recognized words. */
  meanConfidence: number;
}

let workerPromise: Promise<Worker> | null = null;

/**
 * Tesseract worker singleton.
 *
 * Language choice: English-only by default. Adding `chi_sim` is powerful for
 * Chinese packaging scans but ~200ms slower cold-start and adds ~20MB of model
 * downloads — opt-in via `OCR_LANGS` env var for teams that need it.
 */
async function getWorker(): Promise<Worker> {
  if (workerPromise) return workerPromise;
  const langs = process.env.OCR_LANGS || 'eng';
  workerPromise = (async () => {
    const worker = await createWorker(langs.split('+'));
    logger.debug({ langs }, 'tesseract worker initialized');
    return worker;
  })();
  return workerPromise;
}

const STOPWORDS = new Set([
  'the', 'and', 'for', 'with', 'you', 'your', 'this', 'that', 'from', 'have', 'has',
  'are', 'was', 'but', 'not', 'all', 'any', 'can', 'will', 'new', 'our', 'they',
  'per', 'una', 'uno', 'del', 'che', 'con', 'non', 'una', 'alla', 'dal', 'come',
  'www', 'com', 'http', 'https',
]);

/** Extract OCR text + ranked keyword list from a preprocessed image. */
export async function runOcr(imagePath: string): Promise<OcrResult> {
  const started = Date.now();
  try {
    const worker = await getWorker();
    const { data } = await worker.recognize(imagePath);
    const rawText = (data.text || '').trim();
    const meanConfidence = Math.round(data.confidence ?? 0);
    const keywords = extractKeywords(rawText);
    logger.debug(
      { chars: rawText.length, keywords: keywords.length, meanConfidence, elapsedMs: Date.now() - started },
      'ocr done',
    );
    return { text: rawText, keywords, meanConfidence };
  } catch (err) {
    logger.warn({ err: (err as Error).message }, 'ocr failed — returning empty');
    return { text: '', keywords: [], meanConfidence: 0 };
  }
}

export async function shutdownOcr(): Promise<void> {
  if (!workerPromise) return;
  const worker = await workerPromise;
  await worker.terminate();
  workerPromise = null;
}

function extractKeywords(text: string): string[] {
  const tokens = text
    .toLowerCase()
    .replace(/[^a-zà-ÿ0-9\s-]/gi, ' ')
    .split(/\s+/)
    .map((t) => t.trim())
    .filter((t) => t.length >= 3 && !STOPWORDS.has(t));
  const freq = new Map<string, number>();
  for (const t of tokens) freq.set(t, (freq.get(t) ?? 0) + 1);
  return [...freq.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, 10)
    .map(([t]) => t);
}

/** Merge OCR keywords with title-derived keywords into a ranked, deduped list. */
export function buildSearchKeywords(title?: string, ocrKeywords: string[] = []): string[] {
  const out = new Map<string, number>();
  const push = (w: string, weight: number) => {
    const key = w.toLowerCase();
    out.set(key, (out.get(key) ?? 0) + weight);
  };
  if (title) {
    for (const tok of title.split(/[\s,./|•\-—]+/)) {
      const t = tok.trim();
      if (t.length >= 3 && !STOPWORDS.has(t.toLowerCase())) push(t, 2);
    }
  }
  for (const k of ocrKeywords) push(k, 1);
  return [...out.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([t]) => t);
}
