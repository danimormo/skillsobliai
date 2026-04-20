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
const html = readFileSync(path.join(__dirname, 'fixtures', 'temu-pdp.html'), 'utf8');
const $ = cheerio.load(html);

describe('Temu PDP fixture', () => {
  it('reads title from og:title', () => {
    expect(extractTitle($)).toMatch(/Portable Mini Blender/);
  });
  it('parses JSON-LD price + currency', () => {
    expect(extractPrice(html, $)).toEqual({ value: 7.49, currency: 'USD' });
  });
  it('picks the og:image thumbnail with Temu CDN host', () => {
    expect(extractThumbnail($, 'https://www.temu.com/-g-1.html')).toContain('aimg.kwcdn.com');
  });
  it('extracts the 10-day shipping lower bound', () => {
    expect(extractShippingDays($)).toBe(10);
  });
});
