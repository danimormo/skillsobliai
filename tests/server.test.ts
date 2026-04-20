import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import type { Server } from 'node:http';
import { app } from '../src/server.js';

describe('Express app', () => {
  let server: Server;
  let baseUrl: string;

  beforeAll(
    () =>
      new Promise<void>((resolve) => {
        server = app.listen(0, () => {
          const addr = server.address();
          if (addr && typeof addr === 'object') baseUrl = `http://127.0.0.1:${addr.port}`;
          resolve();
        });
      }),
  );

  afterAll(
    () =>
      new Promise<void>((resolve) => {
        server.close(() => resolve());
      }),
  );

  it('GET /health returns a healthy payload', async () => {
    const res = await fetch(`${baseUrl}/health`);
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body).toMatchObject({ status: 'ok', service: 'supplier-finder' });
  });

  it('POST /api/suppliers/find rejects missing source with 400', async () => {
    const res = await fetch(`${baseUrl}/api/suppliers/find`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({}),
    });
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toMatch(/at least one of|invalid/i);
  });

  it('POST /api/suppliers/find rejects non-URL strings with 400', async () => {
    const res = await fetch(`${baseUrl}/api/suppliers/find`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ url: 'not-a-url' }),
    });
    expect(res.status).toBe(400);
  });

  it('POST /api/suppliers/find rejects unknown suppliers with 400', async () => {
    const res = await fetch(`${baseUrl}/api/suppliers/find`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ url: 'https://x.com/a', suppliers: ['NotReal'] }),
    });
    expect(res.status).toBe(400);
  });

  it('propagates x-request-id when supplied, otherwise generates one', async () => {
    const r1 = await fetch(`${baseUrl}/health`, { headers: { 'x-request-id': 'abc-123' } });
    expect(r1.headers.get('x-request-id')).toBe('abc-123');

    const r2 = await fetch(`${baseUrl}/health`);
    expect(r2.headers.get('x-request-id')).toBeTruthy();
  });
});
