import Bottleneck from 'bottleneck';
import { config } from '../config.js';

const limiters = new Map<string, Bottleneck>();

/**
 * Returns a singleton `Bottleneck` limiter scoped to a supplier domain.
 * Enforces: max N concurrent + min interval between requests.
 */
export function getDomainLimiter(domain: string): Bottleneck {
  const key = domain.toLowerCase();
  const existing = limiters.get(key);
  if (existing) return existing;
  const limiter = new Bottleneck({
    maxConcurrent: config.maxConcurrentPerDomain,
    minTime: config.minIntervalMs,
  });
  limiters.set(key, limiter);
  return limiter;
}

export async function shutdownLimiters(): Promise<void> {
  await Promise.all([...limiters.values()].map((l) => l.stop({ dropWaitingJobs: true })));
  limiters.clear();
}
