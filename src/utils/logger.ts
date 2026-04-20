import pino from 'pino';
import { config } from '../config.js';

const isDev = config.nodeEnv !== 'production';

export const logger = pino({
  level: config.logLevel,
  base: { service: 'supplier-finder' },
  timestamp: pino.stdTimeFunctions.isoTime,
  ...(isDev
    ? {
        transport: {
          target: 'pino-pretty',
          options: { colorize: true, translateTime: 'SYS:HH:MM:ss.l' },
        },
      }
    : {}),
});

/** Helper to scope a logger to a given request id. */
export function requestLogger(requestId: string): pino.Logger {
  return logger.child({ requestId });
}

export type Logger = pino.Logger;
