// Shopify Saturation Scanner — orchestration entry point.
//
// Two modes:
//   (1) runScan(input) — synchronous, useful for tests and short scans.
//   (2) BullMQ worker   — production; scans queued from Base44 UI run here.
//
// Streaming: every major milestone emits a "progress" event via the
// onProgress callback (sync mode) OR updates the Bull job with
// updateProgress (worker mode), so Base44 can poll and render live.

import pLimit from "p-limit";
import { Queue, Worker, QueueEvents } from "bullmq";
import IORedis from "ioredis";
import axios from "axios";
import {
  fingerprintFromUrl,
  fingerprintFromImage,
  enrichWithGoogleLens,
  isGenericProduct,
} from "./lib/fingerprint.js";
import { discoverCandidates } from "./lib/discovery.js";
import { validateStore } from "./lib/shopify-validator.js";
import { locateStore } from "./lib/geo-locator.js";
import { scoreSaturation, marketBreakdown } from "./lib/saturation-scorer.js";
import { findOpportunities } from "./lib/opportunity-finder.js";
import { enrichWithAdsStatus } from "./lib/ads-library.js";
import { scanCache, storeCache } from "./lib/cache.js";
import { API_KEYS } from "./config/api-keys.js";
import { THRESHOLDS } from "./config/thresholds.js";

const QUEUE_NAME = "saturation-scans";

function now() { return Date.now(); }

async function notifyTelegram(chatId, text) {
  if (!API_KEYS.telegram.botToken || !chatId) return;
  try {
    await axios.post(
      `https://api.telegram.org/bot${API_KEYS.telegram.botToken}/sendMessage`,
      { chat_id: chatId, text, parse_mode: "Markdown" },
      { timeout: 5_000 },
    );
  } catch { /* notification is best-effort */ }
}

async function buildFingerprint(input) {
  if (input.url) return fingerprintFromUrl(input.url);
  if (input.imageBuffer || input.imageUrl) {
    const buf = input.imageBuffer ??
      (await axios.get(input.imageUrl, { responseType: "arraybuffer" })).data;
    const fp = await fingerprintFromImage(Buffer.from(buf));
    if (input.imageUrl) return enrichWithGoogleLens(fp, input.imageUrl);
    return fp;
  }
  throw new Error("Scan requires either `url` or `imageBuffer`/`imageUrl`");
}

// Core pipeline — also callable directly from tests / a simple HTTP endpoint.
async function runScan(input, { onProgress = () => {} } = {}) {
  const startedAt = now();
  const deadline = startedAt + THRESHOLDS.maxScanDurationMs;

  onProgress({ stage: "fingerprint", pct: 5 });
  const fingerprint = await buildFingerprint(input);

  // Network-effect cache: if we scanned the same fingerprint recently, return it.
  const cached = await scanCache.getFingerprintScan(fingerprint);
  if (cached && !input.forceFresh) {
    onProgress({ stage: "cached", pct: 100 });
    return { ...cached, from_cache: true };
  }

  onProgress({ stage: "discovery", pct: 15, fingerprint });
  const candidates = await discoverCandidates(fingerprint, {
    onBatch: (b) => onProgress({ stage: "discovery", pct: 15 + Math.min(25, b.total / 50), ...b }),
  });

  onProgress({ stage: "validation", pct: 40, candidates: candidates.length });

  // Validate candidates concurrently, but stream hits as they arrive and
  // respect early-stop + deadline.
  const limit = pLimit(THRESHOLDS.storeValidationConcurrency);
  const confirmed = [];
  let stopped = false;
  const tasks = candidates.map((c) => limit(async () => {
    if (stopped) return;
    if (now() > deadline) { stopped = true; return; }
    if (confirmed.length >= THRESHOLDS.maxConfirmedStores) { stopped = true; return; }
    const res = await validateStore(c, fingerprint, { cache: storeCache });
    if (res.matched) {
      confirmed.push(res);
      onProgress({
        stage: "validation",
        pct: 40 + Math.min(30, (confirmed.length / 200) * 30),
        confirmed_count: confirmed.length,
        new_store: res.domain,
      });
      if (confirmed.length >= THRESHOLDS.earlyStopConfirmed) stopped = true;
    }
  }));
  await Promise.all(tasks);

  onProgress({ stage: "geo", pct: 72, confirmed_count: confirmed.length });
  const geoLimit = pLimit(THRESHOLDS.geoLocatorConcurrency);
  const geoLocated = await Promise.all(
    confirmed.map((s) => geoLimit(async () => {
      if (now() > deadline) return { ...s, primary_market: "UNK", geo_confidence: 0 };
      return locateStore(s);
    })),
  );

  onProgress({ stage: "ads", pct: 85 });
  const withAds = await enrichWithAdsStatus(geoLocated, fingerprint, { concurrency: 10 });
  const adsActiveCount = withAds.filter((s) => s.ads_active).length;

  onProgress({ stage: "scoring", pct: 92 });
  const { saturation_score, saturation_zone, components } = scoreSaturation({
    confirmedStores: withAds, adsActiveCount,
  });
  const markets = marketBreakdown(withAds);

  onProgress({ stage: "opportunities", pct: 96 });
  const opp = await findOpportunities({
    marketRows: markets, fingerprint, saturation_zone,
  });

  const result = {
    scan_id: input.scanId ?? `scan_${startedAt}`,
    generated_at: new Date().toISOString(),
    duration_ms: now() - startedAt,
    early_stopped: stopped,
    product_fingerprint: {
      title_normalized: fingerprint.title_normalized,
      image_hash: fingerprint.image_hash,
      identified_by: fingerprint.identified_by,
      raw_title: fingerprint.raw_title,
      keywords: fingerprint.keywords,
      generic_product: isGenericProduct(fingerprint),
      source_url: fingerprint.source_url,
    },
    saturation_score,
    saturation_zone,
    score_components: components,
    total_shopify_stores: withAds.length,
    ads_active_stores: adsActiveCount,
    markets,
    potential_markets: opp.potential_markets,
    blue_ocean_details: opp.blue_ocean_details,
    recommendation: opp.recommendation,
    meta: {
      candidates_inspected: candidates.length,
      ads_library_checked: !!API_KEYS.scrapeCreators,
      cache_mode: "network_effect",
    },
  };

  await scanCache.putFingerprintScan(fingerprint, result);
  onProgress({ stage: "done", pct: 100, result });
  return result;
}

// ── Queue + Worker wiring ──────────────────────────────────────────────────

let _queue = null;
function getQueue() {
  if (_queue) return _queue;
  const connection = new IORedis(API_KEYS.redisUrl, { maxRetriesPerRequest: null });
  _queue = new Queue(QUEUE_NAME, { connection });
  return _queue;
}

async function enqueueScan(input) {
  const q = getQueue();
  const job = await q.add("scan", input, {
    removeOnComplete: 100,
    removeOnFail: 50,
    attempts: 2,
    backoff: { type: "exponential", delay: 10_000 },
  });
  return { jobId: job.id };
}

function startWorker() {
  const connection = new IORedis(API_KEYS.redisUrl, { maxRetriesPerRequest: null });
  const events = new QueueEvents(QUEUE_NAME, { connection });
  events.on("failed", ({ jobId, failedReason }) => {
    console.error(JSON.stringify({ ts: new Date().toISOString(), level: "error", jobId, failedReason }));
  });

  const worker = new Worker(QUEUE_NAME, async (job) => {
    const t0 = now();
    const input = job.data;
    const result = await runScan(input, {
      onProgress: (ev) => job.updateProgress(ev).catch(() => {}),
    });

    if (input.telegramChatId) {
      const emoji = { green: "🟢", yellow: "🟡", red: "🔴" }[result.saturation_zone] ?? "❓";
      await notifyTelegram(
        input.telegramChatId,
        `${emoji} *Scan completato*\n` +
        `Prodotto: \`${result.product_fingerprint.title_normalized || "(image)"}\`\n` +
        `Store totali: *${result.total_shopify_stores}*\n` +
        `Score: *${result.saturation_score}/100* (${result.saturation_zone})\n` +
        `Blue-ocean: ${result.potential_markets.slice(0, 4).join(", ") || "n/a"}\n` +
        `Durata: ${Math.round(result.duration_ms / 1000)}s`,
      );
    }

    console.log(JSON.stringify({
      ts: new Date().toISOString(), level: "info", scan_id: result.scan_id,
      user_id: input.userId ?? null, duration_ms: now() - t0,
      stores: result.total_shopify_stores, zone: result.saturation_zone,
    }));

    return result;
  }, { connection, concurrency: 4 });

  worker.on("error", (err) => {
    console.error(JSON.stringify({ ts: new Date().toISOString(), level: "error", err: err.message }));
  });

  return worker;
}

// CLI: `node index.js --worker` starts the BullMQ consumer on Railway.
if (process.argv.includes("--worker")) {
  startWorker();
  console.log(JSON.stringify({ ts: new Date().toISOString(), level: "info", msg: "worker started" }));
}

export { runScan, enqueueScan, startWorker, getQueue, QUEUE_NAME };
