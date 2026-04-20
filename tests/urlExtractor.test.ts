import { describe, it, expect } from 'vitest';
import * as cheerio from 'cheerio';
import {
  parsePrice,
  pickMainImage,
  pickPrice,
  pickTitle,
} from '../src/input/urlExtractor.js';

const shopifyHtml = `
<!doctype html>
<html><head>
  <meta property="og:image" content="https://cdn.shopify.com/s/files/1/pro.jpg">
  <meta property="og:title" content="Ultra Silent Cat Fountain 2.5L">
  <script type="application/ld+json">
    {"@type":"Product","name":"Cat Fountain","offers":{"@type":"Offer","price":"29.99","priceCurrency":"USD"}}
  </script>
</head><body><h1>Cat Fountain</h1></body></html>`;

describe('urlExtractor helpers', () => {
  it('picks og:image before falling back to <img>', () => {
    const $ = cheerio.load(shopifyHtml);
    expect(pickMainImage($, 'https://brand.com/p/1')).toBe(
      'https://cdn.shopify.com/s/files/1/pro.jpg',
    );
  });

  it('uses relative <img> src when og:image is missing', () => {
    const $ = cheerio.load(
      '<html><body><img src="/img/a.jpg" width="800" height="600"></body></html>',
    );
    expect(pickMainImage($, 'https://shop.example.com/p/1')).toBe(
      'https://shop.example.com/img/a.jpg',
    );
  });

  it('extracts title from og:title first', () => {
    const $ = cheerio.load(shopifyHtml);
    expect(pickTitle($)).toBe('Ultra Silent Cat Fountain 2.5L');
  });

  it('parses JSON-LD price and currency', () => {
    const $ = cheerio.load(shopifyHtml);
    expect(pickPrice($, shopifyHtml)).toEqual({ value: 29.99, currency: 'USD' });
  });

  it('parses European comma-decimal prices', () => {
    expect(parsePrice('19,90')).toBe(19.9);
    expect(parsePrice('1.299,50')).toBe(1299.5);
    expect(parsePrice('$29.99')).toBe(29.99);
    expect(parsePrice('1,299.50')).toBe(1299.5);
  });

  it('returns undefined for garbage', () => {
    expect(parsePrice('N/A')).toBeUndefined();
    expect(parsePrice('')).toBeUndefined();
  });

  it('falls back to heuristic $X.XX when no structured data', () => {
    const noLd = '<html><body><p>Only $12.50 today</p></body></html>';
    const $ = cheerio.load(noLd);
    expect(pickPrice($, noLd)).toEqual({ value: 12.5, currency: 'USD' });
  });
});
