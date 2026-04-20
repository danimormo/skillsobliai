import { describe, it, expect } from 'vitest';
import { existsSync } from 'node:fs';
import { preprocessImage } from '../src/input/imageHandler.js';
import { makeJpegBuffer } from './fixtures/generateImage.js';

describe('preprocessImage', () => {
  it('writes a normalized JPEG from a raw buffer', async () => {
    const buf = await makeJpegBuffer(2000, 1200);
    const out = await preprocessImage({ requestId: 'buf-test', buffer: buf });
    expect(existsSync(out.imagePath)).toBe(true);
    // resize caps longest side at 1024.
    expect(Math.max(out.width, out.height)).toBeLessThanOrEqual(1024);
    expect(out.originalWidth).toBe(2000);
    expect(out.warnings).toHaveLength(0);
  });

  it('emits a low-res warning for images under 300px', async () => {
    const buf = await makeJpegBuffer(200, 200);
    const out = await preprocessImage({ requestId: 'lowres-test', buffer: buf });
    expect(out.warnings.some((w) => /low-resolution/.test(w))).toBe(true);
  });

  it('accepts base64 and strips the data: prefix', async () => {
    const buf = await makeJpegBuffer(400, 400);
    const b64 = 'data:image/jpeg;base64,' + buf.toString('base64');
    const out = await preprocessImage({ requestId: 'b64-test', imageBase64: b64 });
    expect(existsSync(out.imagePath)).toBe(true);
  });

  it('rejects payloads over 10MB', async () => {
    const bigB64 = 'a'.repeat(11 * 1024 * 1024 * 2); // decoded ≈ 11MB+
    await expect(
      preprocessImage({ requestId: 'big-test', imageBase64: bigB64 }),
    ).rejects.toThrow(/10MB/);
  });
});
