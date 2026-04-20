import Redis from 'ioredis';
import { createHash } from 'node:crypto';
import { config } from '../config.js';
import { logger } from './logger.js';

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
