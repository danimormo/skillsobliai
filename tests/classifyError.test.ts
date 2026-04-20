import { describe, it, expect } from 'vitest';
import { classifyError } from '../src/suppliers/base.js';

describe('classifyError', () => {
  it('tags CAPTCHA variants', () => {
    expect(classifyError(new Error('slider captcha detected')).reason).toBe('captcha');
    expect(classifyError(new Error('reCaptcha challenge')).reason).toBe('captcha');
  });

  it('tags timeouts', () => {
    expect(classifyError(new Error('Navigation timeout of 30000 ms exceeded')).reason).toBe(
      'timeout',
    );
    expect(classifyError(new Error('request timed out')).reason).toBe('timeout');
  });

  it('tags blocks and 403s', () => {
    expect(classifyError(new Error('HTTP 403')).reason).toBe('blocked');
    expect(classifyError(new Error('access forbidden by server')).reason).toBe('blocked');
    expect(classifyError(new Error('blocked by anti-bot')).reason).toBe('blocked');
  });

  it('tags network-level failures', () => {
    expect(classifyError(new Error('ENOTFOUND supplier.example')).reason).toBe('network');
    expect(classifyError(new Error('ECONNRESET peer closed')).reason).toBe('network');
  });

  it('tags parse/selector failures', () => {
    expect(classifyError(new Error('selector .foo not found')).reason).toBe('parse');
    expect(classifyError(new Error('parse error on JSON-LD')).reason).toBe('parse');
  });

  it('falls back to unknown for anything unclassified', () => {
    expect(classifyError(new Error('surprise!')).reason).toBe('unknown');
  });

  it('stringifies non-Error throws', () => {
    expect(classifyError('just a string').message).toBe('just a string');
    expect(classifyError(42).message).toBe('42');
  });
});
