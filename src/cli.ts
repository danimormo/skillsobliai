#!/usr/bin/env node
/**
 * Lightweight CLI for manual testing.
 *
 *   npm run find -- --url="https://brand.com/product/xyz"
 *   npm run find -- --image="./product.jpg"
 *   npm run find -- --image="./product.jpg" --suppliers=AliExpress,Shein
 *   npm run find -- --url="…" --no-cache --pretty
 */
import { program } from 'commander';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { findSuppliers } from './index.js';
import { shutdownPipeline } from './shutdown.js';
import { SUPPLIER_NAMES, type FinderInput, type SupplierName } from './types.js';
import { logger } from './utils/logger.js';

program
  .name('supplier-finder')
  .description('Reverse-lookup a product across 9 dropshipping marketplaces')
  .option('--url <url>', 'product URL (Shopify competitor, marketplace page, …)')
  .option('--image <path>', 'local image path (jpg/png/webp, ≤10MB)')
  .option(
    '--suppliers <list>',
    'comma-separated subset (AliExpress,Alibaba,1688,Temu,Shein,Taobao,DHgate,CJDropshipping,Spocket)',
  )
  .option('--no-cache', 'bypass Redis cache for this run')
  .option('--pretty', 'indent JSON output (2 spaces)')
  .parse(process.argv);

const opts = program.opts<{
  url?: string;
  image?: string;
  suppliers?: string;
  cache: boolean; // commander inverts --no-cache → cache: false
  pretty?: boolean;
}>();

async function main(): Promise<void> {
  if (!opts.url && !opts.image) {
    program.error('must provide either --url or --image');
  }
  if (opts.url && opts.image) {
    program.error('--url and --image are mutually exclusive');
  }

  const suppliers = parseSuppliers(opts.suppliers);
  const input: FinderInput = {
    ...(opts.url ? { url: opts.url } : {}),
    ...(opts.image
      ? { imageBase64: (await readFile(path.resolve(opts.image))).toString('base64') }
      : {}),
    ...(suppliers.length > 0 ? { suppliers } : {}),
    ...(opts.cache === false ? { noCache: true } : {}),
  };

  const result = await findSuppliers(input);
  const json = opts.pretty ? JSON.stringify(result, null, 2) : JSON.stringify(result);
  process.stdout.write(json + '\n');
}

function parseSuppliers(raw?: string): SupplierName[] {
  if (!raw) return [];
  const valid = new Set<string>(SUPPLIER_NAMES);
  const out = raw
    .split(',')
    .map((s) => s.trim())
    .filter((s): s is SupplierName => valid.has(s));
  const invalid = raw.split(',').filter((s) => !valid.has(s.trim()));
  if (invalid.length > 0) {
    logger.warn({ invalid }, 'ignoring unknown supplier names');
  }
  return out;
}

main()
  .catch((err) => {
    logger.error({ err: (err as Error).message }, 'CLI run failed');
    process.exitCode = 1;
  })
  .finally(async () => {
    await shutdownPipeline();
  });
