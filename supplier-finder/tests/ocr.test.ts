import { describe, it, expect } from 'vitest';
import { buildSearchKeywords } from '../src/ocr/tesseractEngine.js';

describe('buildSearchKeywords', () => {
  it('weights title tokens higher than OCR keywords', () => {
    const kw = buildSearchKeywords('Wireless Bluetooth Earbuds Pro', [
      'generic',
      'wireless',
      'pro',
    ]);
    // title tokens (weight 2) come first when OCR has single-weight tokens
    expect(kw[0]).toBe('wireless');
    expect(kw).toContain('bluetooth');
    expect(kw).toContain('earbuds');
  });

  it('drops stopwords and short tokens', () => {
    const kw = buildSearchKeywords('The New Pro for You', []);
    expect(kw).not.toContain('the');
    expect(kw).not.toContain('you');
    expect(kw).not.toContain('for');
  });

  it('caps at 8 keywords', () => {
    const title = 'one two three four five six seven eight nine ten eleven twelve';
    const kw = buildSearchKeywords(title, []);
    expect(kw.length).toBeLessThanOrEqual(8);
  });

  it('handles empty title', () => {
    expect(buildSearchKeywords(undefined, ['foo', 'bar'])).toEqual(['foo', 'bar']);
  });

  it('dedupes across title + ocr', () => {
    const kw = buildSearchKeywords('Cat Fountain', ['cat', 'fountain', 'water']);
    const set = new Set(kw);
    expect(set.size).toBe(kw.length);
  });
});
