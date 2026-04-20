#!/usr/bin/env node
/**
 * shopify-product-cloner — universal product cloner entry point.
 *
 *   node clone.js --input <path/to/input.json>
 *
 * Reads input JSON, routes URL, extracts, transforms, imports to Shopify.
 * Logs to stderr with [clone] prefix; emits final JSON result on stdout.
 */

import { readFile } from 'node:fs/promises';
import { log, toHandle, truncateTitle, sanitizeHtml, roundPrice } from './lib/utils.js';
import { resolveRoute } from './lib/url-router.js';
import {
  extractShopifyProduct,
  extractShopifyCollection,
  extractShopifyHomepage,
} from './lib/extractor-shopify.js';
import { extractPlaywrightProduct, extractPlaywrightListing, closePlaywright } from './lib/extractor-playwright.js';
import { ShopifyClient } from './lib/shopify-client.js';
import { transformCopy } from './lib/copy-transformer.js';
import { uploadProductImages } from './lib/image-uploader.js';
import { checkDuplicate } from './lib/dedup.js';

/**
 * Parse minimal CLI flags. Supports --input <path> and --help.
 */
function parseArgs(argv) {
  const args = { input: null, help: false };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--input') args.input = argv[++i];
    else if (a === '--help' || a === '-h') args.help = true;
  }
  return args;
}

function printHelp() {
  process.stderr.write(`Usage: node clone.js --input <path/to/input.json>\n`);
}

/**
 * Load + validate input JSON.
 */
async function loadInput(path) {
  if (!path) throw new Error('Missing --input');
  const raw = await readFile(path, 'utf8');
  const json = JSON.parse(raw);
  const required = ['source_url', 'shopify_shop', 'shopify_access_token'];
  for (const k of required) {
    if (!json[k]) throw new Error(`Missing required field: ${k}`);
  }
  return {
    sourceUrl: json.source_url,
    shop: json.shopify_shop,
    accessToken: json.shopify_access_token,
    options: {
      markupMultiplier: Number(json.options?.markup_multiplier ?? 1.0),
      targetLanguage: json.options?.target_language || null,
      targetMarket: json.options?.target_market || null,
      copyMode: json.options?.copy_mode || 'clone',
      rewriteInstructions: json.options?.rewrite_instructions || null,
      publish: Boolean(json.options?.publish ?? false),
      collectionHandle: json.options?.collection_handle || null,
      maxProducts: Number(json.options?.max_products ?? 100),
    },
  };
}

/**
 * Gather products from the source URL (Shopify native vs Playwright fallback).
 */
async function gatherProducts(sourceUrl, maxProducts) {
  const route = await resolveRoute(sourceUrl);

  if (route.isShopify) {
    if (route.kind === 'product') return [await extractShopifyProduct(route.origin, route.handle)];
    if (route.kind === 'collection') return extractShopifyCollection(route.origin, route.handle, maxProducts);
    return extractShopifyHomepage(route.origin, maxProducts);
  }

  // Non-Shopify
  if (route.kind === 'product') return [await extractPlaywrightProduct(sourceUrl)];
  return extractPlaywrightListing(sourceUrl, maxProducts);
}

/**
 * Build productCreate input + variants payload from an extracted product and options.
 */
function buildProductInput(extracted, transformed, options) {
  const handle = toHandle(transformed.title);
  const title = options.targetMarket ? truncateTitle(transformed.title, 70) : transformed.title;
  const bodyHtml = sanitizeHtml(transformed.bodyHtml);

  const productOptions = (extracted.optionNames || []).map((name) => {
    const values = new Set();
    extracted.variants.forEach((v) => {
      const sel = v.selectedOptions.find((o) => o.name === name);
      if (sel) values.add(sel.value);
    });
    return { name, values: [...values].map((v) => ({ name: v })) };
  });

  const status = options.publish ? 'ACTIVE' : 'DRAFT';

  const productInput = {
    title,
    handle,
    descriptionHtml: bodyHtml,
    vendor: extracted.vendor || undefined,
    productType: extracted.productType || undefined,
    tags: extracted.tags || [],
    status,
    productOptions: productOptions.length ? productOptions : undefined,
  };

  const variantsInput = (extracted.variants || []).map((v) => {
    const price = roundPrice(v.price * options.markupMultiplier, options.targetMarket);
    const compareAtPrice =
      options.markupMultiplier > 1 ? roundPrice(price * 1.3, options.targetMarket) : undefined;
    return {
      price: String(price),
      compareAtPrice: compareAtPrice ? String(compareAtPrice) : undefined,
      sku: v.sku || undefined,
      inventoryItem: v.weight
        ? { measurement: { weight: { value: v.weight, unit: v.weightUnit || 'KILOGRAMS' } } }
        : undefined,
      optionValues: v.selectedOptions.map((so) => ({ optionName: so.name, name: so.value })),
    };
  });

  return { productInput, variantsInput };
}

/**
 * Process a single extracted product end-to-end. Returns a result record.
 */
async function processOne(client, extracted, options) {
  const record = {
    source_url: extracted.sourceUrl,
    shopify_product_id: null,
    shopify_handle: null,
    status: 'error',
  };

  try {
    // 1. Dedup
    const dup = await checkDuplicate(client, { title: extracted.title, sourceUrl: extracted.sourceUrl });
    if (dup.exists) {
      return {
        ...record,
        shopify_product_id: dup.existing?.id || null,
        shopify_handle: dup.existing?.handle || null,
        status: 'skipped',
        skipped_reason: dup.reason,
      };
    }

    // 2. Copy transform
    const transformed = await transformCopy(extracted, {
      mode: options.copyMode,
      targetLanguage: options.targetLanguage,
      instructions: options.rewriteInstructions,
    });

    // 3. Build & create product
    const { productInput, variantsInput } = buildProductInput(extracted, transformed, options);
    log.info(`Creating product: "${productInput.title}" (handle=${productInput.handle}, ${variantsInput.length} variants)`);
    const created = await client.createProduct(productInput);

    // 4. Variants (bulk — productCreate only accepts the first; use bulkCreate for the rest when >1)
    if (variantsInput.length > 0) {
      try {
        await client.createVariants(created.id, variantsInput);
      } catch (err) {
        log.warn(`createVariants failed: ${err.message}`);
      }
    }

    // 5. Metafields: source_url + meta description
    await client.setMetafield(created.id, 'custom', 'source_url', extracted.sourceUrl, 'single_line_text_field');
    const metaDesc = (transformed.bodyHtml || '').replace(/<[^>]+>/g, '').slice(0, 160);
    if (metaDesc) {
      await client.setMetafield(created.id, 'global', 'description_tag', metaDesc, 'single_line_text_field').catch((e) => log.warn(`meta desc failed: ${e.message}`));
    }

    // 6. Images
    const uploaded = await uploadProductImages(client, created.id, transformed.images, transformed.title);

    // 7. Collection assignment
    if (options.collectionHandle) {
      await client.addToCollectionByHandle(created.id, options.collectionHandle);
    }

    return {
      ...record,
      shopify_product_id: created.id,
      shopify_handle: created.handle,
      status: 'created',
      images_uploaded: uploaded,
      variants_count: variantsInput.length,
    };
  } catch (err) {
    log.error(`processOne failed for ${extracted.sourceUrl}: ${err.message}`);
    return { ...record, error: err.message };
  }
}

async function main() {
  const args = parseArgs(process.argv);
  if (args.help || !args.input) {
    printHelp();
    process.exit(args.help ? 0 : 1);
  }

  const cfg = await loadInput(args.input);
  log.info(`Starting clone: ${cfg.sourceUrl} → ${cfg.shop}`);

  const client = new ShopifyClient({ shop: cfg.shop, accessToken: cfg.accessToken });

  let products = [];
  try {
    products = await gatherProducts(cfg.sourceUrl, cfg.options.maxProducts);
  } catch (err) {
    log.error(`Gather failed: ${err.message}`);
    process.stdout.write(
      JSON.stringify([
        { source_url: cfg.sourceUrl, shopify_product_id: null, shopify_handle: null, status: 'error', error: err.message },
      ]) + '\n'
    );
    await closePlaywright();
    process.exit(0);
  }

  log.info(`Gathered ${products.length} product(s) from source`);

  const results = [];
  for (const p of products) {
    const r = await processOne(client, p, cfg.options);
    results.push(r);
  }

  await closePlaywright();

  process.stdout.write(JSON.stringify(results, null, 2) + '\n');
}

main().catch((err) => {
  log.error(`FATAL: ${err.stack || err.message}`);
  process.stdout.write(
    JSON.stringify([{ source_url: null, shopify_product_id: null, shopify_handle: null, status: 'error', error: err.message }]) + '\n'
  );
  closePlaywright().finally(() => process.exit(1));
});
