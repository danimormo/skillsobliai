import { describe, it, expect } from 'vitest';
import { normalizeAnchors } from '../src/visualSearch/candidates.js';

describe('normalizeAnchors', () => {
  it('keeps only http(s) anchors', () => {
    const got = normalizeAnchors(
      [
        { href: 'https://aliexpress.com/item/1' },
        { href: 'javascript:void(0)' },
        { href: 'mailto:a@b.com' },
        { href: 'data:image/png;base64,xxx' },
      ],
      'google-lens',
    );
    expect(got.map((c) => c.url)).toEqual(['https://aliexpress.com/item/1']);
  });

  it('drops google/yandex/bing/microsoft links', () => {
    const got = normalizeAnchors(
      [
        { href: 'https://www.google.com/search?q=x' },
        { href: 'https://images.google.fr/foo' },
        { href: 'https://yandex.com/images/result' },
        { href: 'https://www.bing.com/images' },
        { href: 'https://www.microsoft.com/' },
        { href: 'https://shein.com/product/42' },
      ],
      'google-lens',
    );
    expect(got).toHaveLength(1);
    expect(got[0]!.domain).toBe('shein.com');
  });

  it('dedupes by URL, strips fragments, keeps query string', () => {
    const got = normalizeAnchors(
      [
        { href: 'https://aliexpress.com/item/1?spm=a#top' },
        { href: 'https://aliexpress.com/item/1?spm=a#bottom' },
        { href: 'https://aliexpress.com/item/1?spm=a' },
        { href: 'https://aliexpress.com/item/2' },
      ],
      'google-lens',
    );
    expect(got).toHaveLength(2);
    expect(got[0]!.url).toBe('https://aliexpress.com/item/1?spm=a');
    expect(got[1]!.url).toBe('https://aliexpress.com/item/2');
  });

  it('lower-cases hostname for the domain field', () => {
    const got = normalizeAnchors(
      [{ href: 'https://WWW.ALIEXPRESS.COM/item/9' }],
      'yandex',
    );
    expect(got[0]!.domain).toBe('www.aliexpress.com');
  });

  it('truncates long link text', () => {
    const long = 'x'.repeat(500);
    const got = normalizeAnchors([{ href: 'https://x.com/a', text: long }], 'bing');
    expect(got[0]!.title!.length).toBe(200);
  });

  it('ignores unparseable URLs gracefully', () => {
    const got = normalizeAnchors([{ href: 'not-a-url' }], 'google-lens');
    expect(got).toHaveLength(0);
  });
});
