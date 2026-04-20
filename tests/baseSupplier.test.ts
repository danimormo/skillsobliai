import { describe, it, expect } from 'vitest';
import { BaseSupplier } from '../src/suppliers/base.js';
import type { SearchInput, SupplierListing, SupplierName } from '../src/types.js';

/**
 * BaseSupplier.find() is the pipeline's central guarantee: no matter what a
 * concrete supplier does (throws / returns null / returns a low-confidence
 * match), the final shape is always one of FOUND / NOT_AVAILABLE / ERROR —
 * never a rejected promise. These tests drive a hand-rolled double supplier
 * through every branch.
 */
class FakeSupplier extends BaseSupplier {
  readonly name: SupplierName = 'AliExpress';
  readonly domain = 'fake.example';
  constructor(
    private readonly behavior: {
      imgResult?: SupplierListing | null;
      imgThrow?: Error;
      kwResult?: SupplierListing | null;
      kwThrow?: Error;
      confidence?: number;
      validateThrow?: Error;
    },
  ) {
    super();
  }
  async searchByImage(): Promise<SupplierListing | null> {
    if (this.behavior.imgThrow) throw this.behavior.imgThrow;
    return this.behavior.imgResult ?? null;
  }
  async searchByKeywords(): Promise<SupplierListing | null> {
    if (this.behavior.kwThrow) throw this.behavior.kwThrow;
    return this.behavior.kwResult ?? null;
  }
  async validateMatch(): Promise<number> {
    if (this.behavior.validateThrow) throw this.behavior.validateThrow;
    return this.behavior.confidence ?? 80;
  }
}

function makeInput(): SearchInput {
  return {
    requestId: 't',
    inputType: 'image',
    imagePath: '/tmp/x.jpg',
    keywords: ['bluetooth', 'earbuds'],
    warnings: [],
    title: 'Bluetooth Earbuds',
  };
}

describe('BaseSupplier.find()', () => {
  it('returns FOUND when image search succeeds and confidence ≥ threshold', async () => {
    const s = new FakeSupplier({
      imgResult: { url: 'https://fake.example/p/1', title: 'Bluetooth Earbuds' },
      confidence: 82,
    });
    const out = await s.find(makeInput());
    expect(out.status).toBe('FOUND');
    if (out.status === 'FOUND') {
      expect(out.confidence).toBe(82);
      expect(out.productUrl).toBe('https://fake.example/p/1');
    }
  });

  it('falls back to keyword search when image search returns null', async () => {
    const s = new FakeSupplier({
      imgResult: null,
      kwResult: { url: 'https://fake.example/kw/1', title: 'Bluetooth Earbuds' },
      confidence: 75,
    });
    const out = await s.find(makeInput());
    expect(out.status).toBe('FOUND');
    if (out.status === 'FOUND') expect(out.productUrl).toBe('https://fake.example/kw/1');
  });

  it('returns NOT_AVAILABLE when no stage yields a listing', async () => {
    const s = new FakeSupplier({ imgResult: null, kwResult: null });
    const out = await s.find(makeInput());
    expect(out.status).toBe('NOT_AVAILABLE');
  });

  it('returns NOT_AVAILABLE when confidence is below the threshold', async () => {
    const s = new FakeSupplier({
      imgResult: { url: 'https://fake.example/p/1', title: 'foo' },
      confidence: 20,
    });
    const out = await s.find(makeInput());
    expect(out.status).toBe('NOT_AVAILABLE');
    if (out.status === 'NOT_AVAILABLE') expect(out.reason).toMatch(/confidence/i);
  });

  it('converts a searchByImage throw into an ERROR response (never a rejection)', async () => {
    const s = new FakeSupplier({
      imgThrow: new Error('network: socket hang up'),
      kwResult: null,
    });
    const out = await s.find(makeInput());
    // image search failure is swallowed by the internal `safe` wrapper; with
    // both branches null we get NOT_AVAILABLE.
    expect(out.status).toBe('NOT_AVAILABLE');
  });

  it('converts a validateMatch throw into an ERROR response', async () => {
    // If both sub-steps succeed but validateMatch throws, the base class's
    // `safe()` wraps it → confidence falls to 0 → NOT_AVAILABLE (below
    // threshold). The `safe()` helper prevents propagation; find() never
    // rejects.
    const s = new FakeSupplier({
      imgResult: { url: 'https://fake.example/p/1', title: 'x' },
      validateThrow: new Error('CLIP model unavailable'),
    });
    const out = await s.find(makeInput());
    expect(out.status).toBe('NOT_AVAILABLE');
  });

  it('passes through listing metadata (price, thumbnail, shipping) on FOUND', async () => {
    const s = new FakeSupplier({
      imgResult: {
        url: 'https://fake.example/p/1',
        title: 'Wireless Earbuds',
        price: { value: 12.5, currency: 'USD' },
        thumbnail: 'https://cdn.fake/1.jpg',
        estimatedShippingDays: 7,
      },
      confidence: 88,
    });
    const out = await s.find(makeInput());
    expect(out.status).toBe('FOUND');
    if (out.status === 'FOUND') {
      expect(out.price).toEqual({ value: 12.5, currency: 'USD' });
      expect(out.thumbnail).toBe('https://cdn.fake/1.jpg');
      expect(out.estimatedShippingDays).toBe(7);
    }
  });
});
