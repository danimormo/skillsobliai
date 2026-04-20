import express, { type NextFunction, type Request, type Response } from 'express';
import multer from 'multer';
import { randomUUID } from 'node:crypto';
import { z } from 'zod';
import { findSuppliers } from './index.js';
import { shutdownPipeline } from './shutdown.js';
import { config } from './config.js';
import { logger, requestLogger } from './utils/logger.js';
import { PipelineError, SUPPLIER_NAMES, type FinderInput, type SupplierName } from './types.js';

const app = express();

// 15MB: a 10MB image base64-encoded is ~13.4MB.
app.use(express.json({ limit: '15mb' }));

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 10 * 1024 * 1024 },
});

// Attach a request id to every inbound request for log correlation.
app.use((req, res, next) => {
  const rid = (req.header('x-request-id') || randomUUID()).slice(0, 40);
  (req as Request & { requestId: string }).requestId = rid;
  res.setHeader('x-request-id', rid);
  next();
});

const BodySchema = z.object({
  url: z.string().url().optional(),
  imageBase64: z.string().min(1).optional(),
  suppliers: z.array(z.enum(SUPPLIER_NAMES as readonly [SupplierName, ...SupplierName[]])).optional(),
  noCache: z.boolean().optional(),
});

app.get('/health', (_req, res) => {
  res.json({ status: 'ok', service: 'supplier-finder', version: '0.1.0' });
});

app.post(
  '/api/suppliers/find',
  upload.single('image'),
  async (req: Request, res: Response, next: NextFunction) => {
    const rid = (req as Request & { requestId?: string }).requestId;
    const log = rid ? requestLogger(rid) : logger;
    try {
      let input: FinderInput;

      if (req.file) {
        // Multipart: image file + optional text fields (suppliers, noCache).
        const suppliers = parseSuppliers(req.body?.suppliers);
        input = {
          imageBase64: req.file.buffer.toString('base64'),
          ...(suppliers.length > 0 ? { suppliers } : {}),
          ...(req.body?.noCache === 'true' ? { noCache: true } : {}),
        };
      } else {
        // JSON body.
        const parsed = BodySchema.parse(req.body ?? {});
        input = parsed;
      }

      log.info(
        {
          hasUrl: !!input.url,
          hasImage: !!(input.imageBase64 || input.imagePath),
          suppliers: input.suppliers?.length,
        },
        'REST: find request',
      );

      const result = await findSuppliers(input);
      res.json(result);
    } catch (err) {
      next(err);
    }
  },
);

// Centralized error handler — keeps per-route code focused on the happy path.
app.use((err: unknown, req: Request, res: Response, _next: NextFunction) => {
  const rid = (req as Request & { requestId?: string }).requestId;
  const log = rid ? requestLogger(rid) : logger;

  if (err instanceof z.ZodError) {
    res.status(400).json({ error: 'invalid request body', issues: err.issues });
    return;
  }
  if (err instanceof PipelineError) {
    res.status(400).json({ error: err.message, code: err.reason });
    return;
  }
  if (err && typeof err === 'object' && 'code' in err && err.code === 'LIMIT_FILE_SIZE') {
    res.status(413).json({ error: 'image exceeds 10MB limit' });
    return;
  }
  log.error({ err }, 'unhandled route error');
  res.status(500).json({ error: 'internal error' });
});

function parseSuppliers(raw: unknown): SupplierName[] {
  if (!raw) return [];
  const list = Array.isArray(raw) ? raw : String(raw).split(',');
  const valid = new Set<string>(SUPPLIER_NAMES);
  return list
    .map((s) => (typeof s === 'string' ? s.trim() : ''))
    .filter((s): s is SupplierName => valid.has(s));
}

export { app };

// Start the server only when this module is run directly (not when imported
// as a library, e.g. from tests).
const isMain = import.meta.url === `file://${process.argv[1]}`;
if (isMain) {
  const server = app.listen(config.port, () => {
    logger.info({ port: config.port }, 'supplier-finder server listening');
  });

  const gracefulExit = async (signal: NodeJS.Signals) => {
    logger.info({ signal }, 'received shutdown signal');
    server.close();
    await shutdownPipeline();
    process.exit(0);
  };
  process.on('SIGTERM', gracefulExit);
  process.on('SIGINT', gracefulExit);
}
