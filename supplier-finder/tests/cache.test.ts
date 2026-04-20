import { describe, it, expect, beforeAll } from 'vitest';
import path from 'node:path';
import os from 'node:os';
import { mkdir, writeFile } from 'node:fs/promises';
import { buildCacheKey, hashKey, CACHE_KEY_PREFIX } from '../src/utils/cache.js';
import { makeJpegBuffer } from './fixtures/generateImage.js';

describe('hashKey', () => {
  it('produces a stable digest for the same input', () => {
    expect(hashKey({ a: 1, b: 2 })).toBe(hashKey({ a: 1, b: 2 }));
  });
  it('is sensitive to key order when inputs differ in values', () => {
    expect(hashKey({ a: 1 })).not.toBe(hashKey({ a: 2 }));
  });
});

describe('buildCacheKey', () => {
  const tmp = path.join(os.tmpdir(), 'supplier-finder', 'cache-test');
  let imagePath: string;

  beforeAll(async () => {
    await mkdir(tmp, { recursive: true });
    imagePath = path.join(tmp, 'sample.jpg');
    await writeFile(imagePath, await makeJpegBuffer(400, 400, [10, 10, 10]));
  });

  it('prefixes every key with the library-versioned namespace', async () => {
    const key = await buildCacheKey({ url: 'https://example.com/p/1' });
    expect(key.startsWith(`${CACHE_KEY_PREFIX}:`)).toBe(true);
  });

  it('is stable across calls with identical input', async () => {
    const k1 = await buildCacheKey({ url: 'https://a.com/x' });
    const k2 = await buildCacheKey({ url: 'https://a.com/x' });
    expect(k1).toBe(k2);
  });

  it('differs when the URL changes', async () => {
    const k1 = await buildCacheKey({ url: 'https://a.com/x' });
    const k2 = await buildCacheKey({ url: 'https://a.com/y' });
    expect(k1).not.toBe(k2);
  });

  it('differs when the suppliers filter changes', async () => {
    const full = await buildCacheKey({ url: 'https://a.com/x' });
    const filtered = await buildCacheKey({
      url: 'https://a.com/x',
      suppliers: ['AliExpress', 'Shein'],
    });
    expect(full).not.toBe(filtered);
  });

  it('orders the suppliers filter deterministically', async () => {
    const a = await buildCacheKey({
      url: 'https://a.com/x',
      suppliers: ['Shein', 'AliExpress'],
    });
    const b = await buildCacheKey({
      url: 'https://a.com/x',
      suppliers: ['AliExpress', 'Shein'],
    });
    expect(a).toBe(b);
  });

  it('hashes image base64 input distinctly from url input', async () => {
    const urlKey = await buildCacheKey({ url: 'https://a.com/x' });
    const imgKey = await buildCacheKey({ imageBase64: 'AAAA' });
    expect(urlKey).not.toBe(imgKey);
  });

  it('hashes image file content from imagePath', async () => {
    const k1 = await buildCacheKey({ imagePath });
    const k2 = await buildCacheKey({ imagePath });
    expect(k1).toBe(k2);
  });
});
