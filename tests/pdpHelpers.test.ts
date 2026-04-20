import { describe, it, expect } from 'vitest';
import * as cheerio from 'cheerio';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  extractPrice,
  extractShippingDays,
  extractThumbnail,
  extractTitle,
  validateListing,
} from '../src/suppliers/pdp.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const html = readFileSync(path.join(__dirname, 'fixtures', 'aliexpress-pdp.html'), 'utf8');
const $ = cheerio.load(html);

describe('pdp helpers against the AliExpress fixture', () => {
  it('extracts the product title from og:title', () => {
    expect(extractTitle($)).toBe('Ultra Silent Pet Water Fountain 2.5L');
  });

  it('extracts price and currency from JSON-LD Offer', () => {
    expect(extractPrice(html, $)).toEqual({ value: 12.99, currency: 'USD' });
  });

  it('extracts the OG image as thumbnail', () => {
    expect(extractThumbnail($, 'https://www.aliexpress.com/item/1.html')).toBe(
      'https://ae01.alicdn.com/kf/S1234567890.jpg',
    );
  });

  it('picks the lower bound of the shipping range', () => {
    expect(extractShippingDays($)).toBe(8);
  });

  it('parses og:price:amount when JSON-LD is absent', () => {
    const h2 = `<html><head>
      <meta property="og:price:amount" content="9.50">
      <meta property="og:price:currency" content="EUR">
    </head><body></body></html>`;
    const $2 = cheerio.load(h2);
    expect(extractPrice(h2, $2)).toEqual({ value: 9.5, currency: 'EUR' });
  });

  it('falls back to heuristic "$X.XX" text match', () => {
    const h3 = '<html><body><p>Only $4.25 today</p></body></html>';
    const $3 = cheerio.load(h3);
    expect(extractPrice(h3, $3)).toEqual({ value: 4.25, currency: 'USD' });
  });
});

describe('validateListing scoring (text-only path)', () => {
  it('returns a capped score (≤60) when no embedding is provided', async () => {
    const score = await validateListing({
      requestId: 'test-no-clip',
      supplier: 'AliExpress',
      listing: {
        url: 'https://www.aliexpress.com/item/1.html',
        title: 'Ultra Silent Pet Water Fountain 2.5L',
      },
      referenceTitle: 'Ultra Silent Pet Water Fountain 2.5L',
      referenceKeywords: ['fountain', 'pet', 'silent'],
    });
    expect(score).toBeGreaterThan(0);
    expect(score).toBeLessThanOrEqual(60);
  });

  it('returns a lower score for mismatching titles', async () => {
    const good = await validateListing({
      requestId: 'test-good',
      supplier: 'AliExpress',
      listing: { url: 'x', title: 'Bluetooth Earbuds' },
      referenceTitle: 'Bluetooth Earbuds',
      referenceKeywords: ['bluetooth', 'earbuds'],
    });
    const bad = await validateListing({
      requestId: 'test-bad',
      supplier: 'AliExpress',
      listing: { url: 'x', title: 'Bluetooth Earbuds' },
      referenceTitle: 'Garden Hose 50ft',
      referenceKeywords: ['garden', 'hose'],
    });
    expect(good).toBeGreaterThan(bad);
  });
});
