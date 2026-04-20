import { describe, it, expect } from 'vitest';
import { AliExpressSupplier } from '../src/suppliers/aliexpress.js';

describe('AliExpressSupplier', () => {
  const s = new AliExpressSupplier();

  it('has the expected name and domain', () => {
    expect(s.name).toBe('AliExpress');
    expect(s.domain).toBe('aliexpress.com');
  });

  it('returns null from searchByImage when no aliexpress candidate was found', async () => {
    const result = await s.searchByImage({
      requestId: 't',
      inputType: 'image',
      imagePath: '/tmp/x.jpg',
      keywords: [],
      warnings: [],
      candidates: [
        {
          url: 'https://example.com/p/1',
          source: 'google-lens',
          domain: 'example.com',
        },
      ],
    });
    expect(result).toBeNull();
  });

  it('returns null from searchByKeywords when keywords are empty', async () => {
    const result = await s.searchByKeywords({
      requestId: 't',
      inputType: 'image',
      imagePath: '/tmp/x.jpg',
      keywords: [],
      warnings: [],
    });
    expect(result).toBeNull();
  });
});
