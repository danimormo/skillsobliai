import { describe, it, expect } from 'vitest';
import { matchSupplier, isSupplierDomain, SUPPLIER_DOMAINS } from '../src/visualSearch/domains.js';

describe('matchSupplier', () => {
  it('matches exact domains', () => {
    expect(matchSupplier('aliexpress.com')).toBe('AliExpress');
    expect(matchSupplier('1688.com')).toBe('1688');
    expect(matchSupplier('temu.com')).toBe('Temu');
  });

  it('matches subdomains via suffix rule', () => {
    expect(matchSupplier('m.aliexpress.com')).toBe('AliExpress');
    expect(matchSupplier('id.shein.com')).toBe('Shein');
    expect(matchSupplier('detail.tmall.com')).toBe('Taobao');
    expect(matchSupplier('www.cjdropshipping.com')).toBe('CJDropshipping');
  });

  it('is case-insensitive', () => {
    expect(matchSupplier('Aliexpress.Com')).toBe('AliExpress');
  });

  it('rejects unrelated domains', () => {
    expect(matchSupplier('example.com')).toBeUndefined();
    expect(matchSupplier('google.com')).toBeUndefined();
  });

  it('does NOT match partial-suffix collisions', () => {
    // "notaliexpress.com" should not match "aliexpress.com"
    expect(matchSupplier('notaliexpress.com')).toBeUndefined();
  });
});

describe('isSupplierDomain', () => {
  it('returns true for any mapped supplier', () => {
    for (const d of Object.values(SUPPLIER_DOMAINS).flat()) {
      expect(isSupplierDomain(d)).toBe(true);
    }
  });
  it('returns false otherwise', () => {
    expect(isSupplierDomain('random.site')).toBe(false);
  });
});
