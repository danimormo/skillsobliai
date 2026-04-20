# Integrating the Saturation Scanner

The scanner is a Node.js microservice shipped under
`skills/shopify-saturation-scanner/`. It runs independently from the Python
FastAPI monolith (this repo's `main.py`) because:

- it uses Node-only libs (`sharp`, `image-hash`, `bullmq`);
- it's cheaper to scale the queue worker independently on Railway.

## Backend HTTP contract (Base44 → Node service)

The React component (`Base44Scanner.jsx`) assumes two endpoints:

### POST `/api/saturation-scan`

Kicks off an async scan and returns immediately.

Accepts either:
- `Content-Type: application/json` with `{ url, userId }`, or
- `multipart/form-data` with an `image` file + `userId`.

Returns `{ jobId: "..." }`.

Implementation example (Fastify/Express handler):

```js
import { enqueueScan } from "../shopify-saturation-scanner/index.js";

app.post("/api/saturation-scan", async (req, res) => {
  const { url, userId } = req.body;
  const imageBuffer = req.file?.buffer;
  const { jobId } = await enqueueScan({ url, userId, imageBuffer });
  res.json({ jobId });
});
```

### GET `/api/saturation-scan/:jobId`

Returns `{ status, progress, result, error }`.

```js
import { getQueue } from "../shopify-saturation-scanner/index.js";

app.get("/api/saturation-scan/:jobId", async (req, res) => {
  const job = await getQueue().getJob(req.params.jobId);
  if (!job) return res.status(404).json({ error: "not_found" });
  const state = await job.getState();
  res.json({
    status: state === "completed" ? "done" : state === "failed" ? "failed" : state,
    progress: job.progress,
    result: state === "completed" ? job.returnvalue : null,
    error: state === "failed" ? job.failedReason : null,
  });
});
```

## Python FastAPI bridge (optional)

If you prefer to proxy through the existing FastAPI stack instead of running
Node directly:

```python
# core/http_client.py is already in the repo.
import httpx
SCANNER_URL = os.getenv("SATURATION_SCANNER_URL")  # e.g. http://scanner.railway.internal

async def enqueue_scan(payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(f"{SCANNER_URL}/api/saturation-scan", json=payload)
        r.raise_for_status()
        return r.json()
```

Add a thin FastAPI router under `SKILLS/24_saturation_scanner_v2/router.py`
that forwards to the Node service — keeps Base44's "one Python backend"
mental model without blocking the Node queue.

## Running locally

```bash
cd skills/shopify-saturation-scanner
npm install
cp ../../.env.example .env       # add SERPAPI_API_KEY, REDIS_URL, SUPABASE_*
npm run worker                   # consumer
node -e "import('./index.js').then(m => m.runScan({url:'https://...'}).then(console.log))"
```

For Railway:

```toml
# railway.toml excerpt
[services.scanner]
build.command = "cd skills/shopify-saturation-scanner && npm ci"
deploy.startCommand = "cd skills/shopify-saturation-scanner && node index.js --worker"
```
