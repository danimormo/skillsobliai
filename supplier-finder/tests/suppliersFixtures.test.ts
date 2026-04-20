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
} from '../src/suppliers/pdp.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
function loadFixture(name: string): { html: string; $: cheerio.CheerioAPI } {
  const html = readFileSync(path.join(__dirname, 'fixtures', name), 'utf8');
  return { html, $: cheerio.load(html) };
}

describe('Shein PDP fixture', () => {
  const { html, $ } = loadFixture('shein-pdp.html');

  it('reads title from og:title', () => {
    expect(extractTitle($)).toMatch(/SHEIN Summer Midi Dress/);
  });

  it('reads price+currency from JSON-LD Offer', () => {
    expect(extractPrice(html, $)).toEqual({ value: 14.99, currency: 'USD' });
  });

  it('picks the og:image thumbnail', () => {
    expect(extractThumbnail($, 'https://us.shein.com/dress-p-123.html')).toBe(
      'https://img.ltwebstatic.com/images/v1/shein-p-123.webp',
    );
  });

  it('extracts the 6-9 day shipping lower bound', () => {
    expect(extractShippingDays($)).toBe(6);
  });
});

describe('1688 PDP fixture', () => {
  const { html, $ } = loadFixture('1688-pdp.html');

  it('reads Chinese title from og:title', () => {
    expect(extractTitle($)).toContain('宠物饮水机');
  });

  it('parses CNY price from og:price:amount', () => {
    expect(extractPrice(html, $)).toEqual({ value: 29.5, currency: 'CNY' });
  });

  it('extracts the 3-7 day shipping lower bound', () => {
    expect(extractShippingDays($)).toBe(3);
  });
});
