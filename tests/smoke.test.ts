import { describe, it, expect } from 'vitest';
import { findSuppliers, SUPPLIER_NAMES } from '../src/index.js';

describe('Step 1 skeleton', () => {
  it('returns one entry per supplier with NOT_AVAILABLE by default', async () => {
    const out = await findSuppliers({ url: 'https://example.com/product/123' });
    expect(out.results).toHaveLength(SUPPLIER_NAMES.length);
    for (const r of out.results) {
      expect(r.status).toBe('NOT_AVAILABLE');
    }
    expect(out.query.inputType).toBe('url');
    expect(out.executionTimeMs).toBeGreaterThanOrEqual(0);
  });

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

  it('honors suppliers filter', async () => {
    const out = await findSuppliers({
      url: 'https://example.com/x',
      suppliers: ['AliExpress', 'Shein'],
    });
    expect(out.results).toHaveLength(2);
    expect(out.results.map((r) => r.supplier).sort()).toEqual(['AliExpress', 'Shein']);
  });
});
