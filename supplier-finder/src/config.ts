import 'dotenv/config';

function num(name: string, fallback: number): number {
  const raw = process.env[name];
  if (!raw) return fallback;
  const n = Number(raw);
  return Number.isFinite(n) ? n : fallback;
}

function str(name: string, fallback: string): string {
  return process.env[name] ?? fallback;
}

function bool(name: string, fallback: boolean): boolean {
  const raw = process.env[name];
  if (raw === undefined) return fallback;
  return raw === 'true' || raw === '1';
}

export const config = {
  nodeEnv: str('NODE_ENV', 'development'),
  logLevel: str('LOG_LEVEL', 'info'),
  port: num('PORT', 8787),

  redisUrl: process.env.REDIS_URL,
  cacheTtlSeconds: num('CACHE_TTL_SECONDS', 86400),

  minConfidence: num('MIN_CONFIDENCE', 50),
  ambiguousConfidence: num('AMBIGUOUS_CONFIDENCE', 70),

  headless: bool('HEADLESS', true),
  browserTimeoutMs: num('BROWSER_TIMEOUT_MS', 30000),
  actionDelayMinMs: num('ACTION_DELAY_MIN_MS', 500),
  actionDelayMaxMs: num('ACTION_DELAY_MAX_MS', 2000),
  proxyUrl: process.env.PROXY_URL,

  maxConcurrentPerDomain: num('MAX_CONCURRENT_PER_DOMAIN', 3),
  minIntervalMs: num('MIN_INTERVAL_MS', 1000),

  pipelineTimeoutMs: num('PIPELINE_TIMEOUT_MS', 15000),
  supplierTimeoutMs: num('SUPPLIER_TIMEOUT_MS', 12000),
} as const;

export type Config = typeof config;
