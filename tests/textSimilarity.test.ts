import { describe, it, expect } from 'vitest';
import {
  levenshtein,
  textSimilarity,
  tokenOverlap,
  titleScore,
  keywordHitRate,
} from '../src/matching/textSimilarity.js';

describe('levenshtein', () => {
  it('returns 0 for identical strings', () => {
    expect(levenshtein('abc', 'abc')).toBe(0);
  });
  it('handles empty inputs', () => {
    expect(levenshtein('', 'abc')).toBe(3);
    expect(levenshtein('abc', '')).toBe(3);
  });
  it('matches known distances', () => {
    expect(levenshtein('kitten', 'sitting')).toBe(3);
    expect(levenshtein('cat fountain', 'cat fountan')).toBe(1);
  });
});

describe('textSimilarity', () => {
  it('is 100 for identical strings after normalization', () => {
    expect(textSimilarity('Cat Fountain', '  cat   fountain  ')).toBe(100);
  });
  it('is symmetric', () => {
    expect(textSimilarity('abc', 'abcd')).toBe(textSimilarity('abcd', 'abc'));
  });
  it('drops significantly for very different strings', () => {
    expect(textSimilarity('cat fountain', 'dog leash')).toBeLessThan(50);
  });
});

describe('tokenOverlap', () => {
  it('is 100 for identical token sets', () => {
    expect(tokenOverlap('cat fountain 2.5L', 'Fountain cat 2.5l')).toBe(100);
  });
  it('is 0 for disjoint token sets', () => {
    expect(tokenOverlap('red bike', 'blue car')).toBe(0);
  });
  it('handles diacritics uniformly', () => {
    expect(tokenOverlap('café noir', 'cafe noir')).toBe(100);
  });
});

describe('titleScore', () => {
  it('uses max(jaccard, levenshtein)', () => {
    // Reordered title → jaccard high, levenshtein low; max should be high.
    expect(titleScore('Wireless Bluetooth Earbuds', 'Earbuds Bluetooth Wireless')).toBeGreaterThan(80);
  });
  it('returns 0 for unrelated strings', () => {
    expect(titleScore('banana', 'titanium drill')).toBeLessThan(30);
  });
});

describe('keywordHitRate', () => {
  it('counts substring hits', () => {
    expect(keywordHitRate(['bluetooth', 'earbuds'], 'Pro Bluetooth Earbuds v2')).toBe(100);
  });
  it('is 0 on empty keyword list', () => {
    expect(keywordHitRate([], 'anything')).toBe(0);
  });
  it('handles case insensitively', () => {
    expect(keywordHitRate(['CAT'], 'cat fountain')).toBe(100);
  });
});
