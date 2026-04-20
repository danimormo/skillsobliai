import { describe, it, expect } from 'vitest';
import { cosineSimilarity, similarityScore } from '../src/matching/clipSimilarity.js';

describe('cosineSimilarity', () => {
  it('is 1 for identical vectors', () => {
    const v = new Float32Array([0.5, 0.5, 0.5, 0.5]);
    expect(cosineSimilarity(v, v)).toBeCloseTo(1, 5);
  });

  it('is 0 for orthogonal vectors', () => {
    const a = new Float32Array([1, 0, 0, 0]);
    const b = new Float32Array([0, 1, 0, 0]);
    expect(cosineSimilarity(a, b)).toBeCloseTo(0, 5);
  });

  it('is -1 for opposite vectors', () => {
    const a = new Float32Array([1, 2, 3]);
    const b = new Float32Array([-1, -2, -3]);
    expect(cosineSimilarity(a, b)).toBeCloseTo(-1, 5);
  });

  it('throws on length mismatch', () => {
    expect(() => cosineSimilarity(new Float32Array([1, 2]), new Float32Array([1, 2, 3]))).toThrow(
      /length mismatch/,
    );
  });

  it('handles zero vectors without NaN', () => {
    const z = new Float32Array([0, 0, 0]);
    expect(cosineSimilarity(z, z)).toBe(0);
  });
});

describe('similarityScore', () => {
  it('maps identity to 100', () => {
    const v = new Float32Array([1, 0, 0]);
    expect(similarityScore(v, v)).toBe(100);
  });
  it('clamps negatives to 0', () => {
    const a = new Float32Array([1, 0]);
    const b = new Float32Array([-1, 0]);
    expect(similarityScore(a, b)).toBe(0);
  });
  it('is symmetric', () => {
    const a = new Float32Array([1, 2, 3]);
    const b = new Float32Array([2, 1, 4]);
    expect(similarityScore(a, b)).toBe(similarityScore(b, a));
  });
});
