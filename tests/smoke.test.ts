import { describe, it, expect } from 'vitest';
import { findSuppliers } from '../src/index.js';

/**
 * Validation-only smoke tests. Happy-path pipeline execution is covered by
 * the dedicated stage tests (imageHandler / urlExtractor / ocr) and by the
 * opt-in integration test that needs Playwright + network.
 */
describe('findSuppliers input validation', () => {
  it('rejects input with no source', async () => {
    await expect(findSuppliers({})).rejects.toThrow(/at least one of/i);
  });

  it('rejects input with multiple sources', async () => {
    await expect(
      findSuppliers({ url: 'https://x.com/a', imagePath: '/tmp/a.jpg' }),
    ).rejects.toThrow(/exactly one input source/i);
  });

  it('rejects non-http URL', async () => {
    await expect(findSuppliers({ url: 'file:///etc/passwd' })).rejects.toThrow(/http\(s\)/i);
  });
});
