/**
 * Opt-in e2e test that actually downloads the CLIP model and runs inference.
 *
 * First run fetches ~50MB of weights from HuggingFace → can take a minute
 * on cold CI. Enable with:
 *
 *   RUN_CLIP_E2E=1 npm test -- clipEmbedding
 */
import { describe, it, expect } from 'vitest';
import path from 'node:path';
import os from 'node:os';
import { mkdir, writeFile } from 'node:fs/promises';
import { makeJpegBuffer } from './fixtures/generateImage.js';
import { embedImage, EMBEDDING_DIM, similarityScore } from '../src/matching/clipSimilarity.js';

const runE2E = process.env.RUN_CLIP_E2E === '1';
const d = runE2E ? describe : describe.skip;

d('CLIP embedding (e2e)', () => {
  const tmp = path.join(os.tmpdir(), 'supplier-finder', 'clip-e2e');

  it(
    'produces a 512-dim normalized embedding and rates self-similarity at 100',
    async () => {
      await mkdir(tmp, { recursive: true });
      const red = path.join(tmp, 'red.jpg');
      const blue = path.join(tmp, 'blue.jpg');
      await writeFile(red, await makeJpegBuffer(384, 384, [220, 30, 30]));
      await writeFile(blue, await makeJpegBuffer(384, 384, [30, 30, 220]));

      const a = await embedImage(red);
      const b = await embedImage(red);
      const c = await embedImage(blue);

      expect(a.length).toBe(EMBEDDING_DIM);
      expect(similarityScore(a, b)).toBe(100);
      // Solid-color reds vs blues aren't "opposite" in CLIP space but should
      // still be measurably less similar than two reds.
      expect(similarityScore(a, c)).toBeLessThan(100);
    },
    120_000,
  );
});
