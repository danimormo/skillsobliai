import { describe, it, expect } from 'vitest';
import { SUPPLIER_REGISTRY, getSupplier } from '../src/suppliers/registry.js';
import { SUPPLIER_NAMES } from '../src/types.js';

describe('SUPPLIER_REGISTRY', () => {
  it('defines an implementation for every canonical supplier name', () => {
    for (const name of SUPPLIER_NAMES) {
      const impl = getSupplier(name);
      expect(impl, `missing implementation for ${name}`).toBeDefined();
      expect(impl!.name).toBe(name);
      expect(impl!.domain).toBeTruthy();
    }
  });

  it('has no duplicate (name, domain) pairs', () => {
    const pairs = new Set<string>();
    for (const impl of Object.values(SUPPLIER_REGISTRY)) {
      const key = `${impl.name}|${impl.domain}`;
      expect(pairs.has(key), `duplicate ${key}`).toBe(false);
      pairs.add(key);
    }
  });

  it('every supplier returns null from searchByKeywords on empty input', async () => {
    for (const impl of Object.values(SUPPLIER_REGISTRY)) {
      const out = await impl.searchByKeywords({
        requestId: 't',
        inputType: 'image',
        imagePath: '/tmp/x.jpg',
        keywords: [],
        warnings: [],
      });
      expect(out, `supplier ${impl.name} should return null on empty keywords`).toBeNull();
    }
  });

  it('every supplier returns null from searchByImage when candidates are foreign', async () => {
    for (const impl of Object.values(SUPPLIER_REGISTRY)) {
      const out = await impl.searchByImage({
        requestId: 't',
        inputType: 'image',
        imagePath: '/tmp/x.jpg',
        keywords: [],
        warnings: [],
        candidates: [
          {
            url: 'https://unrelated.example/p/1',
            source: 'google-lens',
            domain: 'unrelated.example',
          },
        ],
      });
      expect(out, `supplier ${impl.name} should not match unrelated candidates`).toBeNull();
    }
  });
});
