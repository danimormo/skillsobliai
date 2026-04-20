import Redis from 'ioredis';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { config } from '../config.js';
import { logger } from './logger.js';
import type { FinderInput } from '../types.js';

let client: Redis | null = null;
let connectionFailed = false;

function getClient(): Redis | null {
  if (connectionFailed) return null;
  if (client) return client;
  if (!config.redisUrl) return null;
  try {
    client = new Redis(config.redisUrl, {
      lazyConnect: false,
      maxRetriesPerRequest: 1,
      enableOfflineQueue: false,
    });
    client.on('error', (err) => {
      if (!connectionFailed) {
        logger.warn({ err: err.message }, 'Redis error — falling back to no-cache mode');
        connectionFailed = true;
      }
    });
    return client;
  } catch (err) {
    connectionFailed = true;
    logger.warn({ err }, 'Redis init failed — running without cache');
    return null;
  }
}

/** Stable hash of a JSON-serializable payload. */
export function hashKey(payload: unknown): string {
  const json = JSON.stringify(payload);
  return createHash('sha256').update(json).digest('hex').slice(0, 24);
}

export async function cacheGet<T>(key: string): Promise<T | null> {
  const c = getClient();
  if (!c) return null;
  try {
    const raw = await c.get(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch (err) {
    logger.warn({ err, key }, 'cacheGet failed');
    return null;
  }
}

export async function cacheSet(
  key: string,
  value: unknown,
  ttlSeconds = config.cacheTtlSeconds,
): Promise<void> {
  const c = getClient();
  if (!c) return;
  try {
    await c.set(key, JSON.stringify(value), 'EX', ttlSeconds);
  } catch (err) {
    logger.warn({ err, key }, 'cacheSet failed');
  }
}

export async function closeCache(): Promise<void> {
  if (client) {
    await client.quit().catch(() => {});
    client = null;
  }
}

export const CACHE_KEY_PREFIX = 'supplier-finder:v1';

/**
 * Build a deterministic cache key from the user-facing FinderInput.
 *
 * The key depends on:
 *   - source (url | image bytes) — image is hashed to avoid blowing up key size
 *   - sorted list of target suppliers (same inputs + different supplier filter
 *     must miss the cache, since the response shape differs)
 *
 * Hashing the raw image bytes (not the preprocessed JPEG) is intentional:
 *   - it's O(image size), ~50ms for a 10MB base64 → acceptable to do before
 *     preprocessing
 *   - it means two logically identical uploads hit the same cache row even
 *     if preprocessing ever changes across library versions
 */
export async function buildCacheKey(input: FinderInput): Promise<string> {
  const suppliers = input.suppliers ? [...input.suppliers].sort() : ['*'];
  let source: string;
  if (input.url) {
    source = `url:${input.url}`;
  } else if (input.imageBase64) {
    source = `imgB64:${sha256(input.imageBase64)}`;
  } else if (input.imagePath) {
    const buf = await readFile(input.imagePath);
    source = `imgPath:${sha256(buf)}`;
  } else {
    source = 'empty';
  }
  const payload = { source, suppliers };
  return `${CACHE_KEY_PREFIX}:${hashKey(payload)}`;
}

function sha256(data: string | Buffer): string {
  return createHash('sha256').update(data).digest('hex');
}
