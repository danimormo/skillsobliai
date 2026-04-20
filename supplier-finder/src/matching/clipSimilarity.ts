/**
 * Local image embeddings with CLIP ViT-B/32 via @xenova/transformers.
 *
 * Why low-level (AutoProcessor + CLIPVisionModelWithProjection) instead of
 * the `image-feature-extraction` pipeline:
 *   - The pipeline returns the encoder hidden state (768-dim, unprojected).
 *   - For image-image similarity we want the *projection* head output
 *     (512-dim), which is the space in which CLIP was trained for retrieval.
 *   - Explicit L2 normalization makes cosine similarity equal to a dot
 *     product → faster and bit-identical between runs.
 */
import {
  AutoProcessor,
  CLIPVisionModelWithProjection,
  RawImage,
  type PreTrainedModel,
  type Processor,
} from '@xenova/transformers';
import { logger } from '../utils/logger.js';

const MODEL_ID = 'Xenova/clip-vit-base-patch32';
export const EMBEDDING_DIM = 512;

let processorPromise: Promise<Processor> | null = null;
let modelPromise: Promise<PreTrainedModel> | null = null;

async function getModel(): Promise<{ processor: Processor; model: PreTrainedModel }> {
  if (!processorPromise) {
    processorPromise = AutoProcessor.from_pretrained(MODEL_ID).then((p) => {
      logger.debug({ model: MODEL_ID }, 'clip processor ready');
      return p;
    });
  }
  if (!modelPromise) {
    modelPromise = CLIPVisionModelWithProjection.from_pretrained(MODEL_ID, {
      quantized: true, // 4x smaller weights, ~1% accuracy drop — fine for product matching.
    }).then((m) => {
      logger.debug({ model: MODEL_ID }, 'clip vision model ready');
      return m;
    });
  }
  const [processor, model] = await Promise.all([processorPromise, modelPromise]);
  return { processor, model };
}

/** Compute an L2-normalized 512-dim embedding for the image at `imagePath`. */
export async function embedImage(imagePath: string): Promise<Float32Array> {
  const { processor, model } = await getModel();
  const image = await RawImage.read(imagePath);
  const inputs = await processor(image);
  const output = (await model(inputs)) as { image_embeds: { data: Float32Array } };
  const raw = output.image_embeds.data;
  return l2Normalize(raw);
}

/** Cosine similarity in [-1, 1]. Assumes both vectors are the same length. */
export function cosineSimilarity(a: Float32Array, b: Float32Array): number {
  if (a.length !== b.length) {
    throw new Error(`embedding length mismatch: ${a.length} vs ${b.length}`);
  }
  let dot = 0;
  let na = 0;
  let nb = 0;
  for (let i = 0; i < a.length; i++) {
    const ai = a[i]!;
    const bi = b[i]!;
    dot += ai * bi;
    na += ai * ai;
    nb += bi * bi;
  }
  const denom = Math.sqrt(na) * Math.sqrt(nb);
  return denom === 0 ? 0 : dot / denom;
}

/**
 * Map cosine similarity to a 0-100 confidence.
 *
 * CLIP image-image cosine on real product photos clusters in 0.2-0.9.
 * We clamp negatives to 0 (no meaningful info there) and multiply the
 * positive half by 100 — linear and interpretable.
 */
export function similarityScore(a: Float32Array, b: Float32Array): number {
  const sim = cosineSimilarity(a, b);
  return Math.max(0, Math.min(100, Math.round(sim * 100)));
}

function l2Normalize(v: Float32Array): Float32Array {
  let sum = 0;
  for (let i = 0; i < v.length; i++) sum += v[i]! * v[i]!;
  const norm = Math.sqrt(sum);
  if (norm === 0) return v;
  const out = new Float32Array(v.length);
  for (let i = 0; i < v.length; i++) out[i] = v[i]! / norm;
  return out;
}
