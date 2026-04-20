// Multi-source Shopify store discovery.
// Source A: SerpAPI Google SERP targeted queries.
// Source B: seeded dataset (data/shopify_sample_stores.json from the repo).
// Source C: Google CSE fallback when SerpAPI unavailable.
//
// Produces a candidate list of domains that MIGHT sell the product. These
// are then validated by shopify-validator.js.

import axios from "axios";
import pLimit from "p-limit";
import { getJson } from "serpapi";
import { API_KEYS } from "../config/api-keys.js";
import { THRESHOLDS } from "../config/thresholds.js";

// Language-varied query templates. The {kw} placeholder is filled with the
// product keyword(s). We probe multiple markets so discovery isn't US-biased.
const QUERY_TEMPLATES = [
  { lang: "en", hl: "en", gl: "us", q: `"{kw}" site:*.myshopify.com` },
  { lang: "en", hl: "en", gl: "us", q: `"{kw}" "Powered by Shopify"` },
  { lang: "en", hl: "en", gl: "gb", q: `"{kw}" "Powered by Shopify"` },
  { lang: "de", hl: "de", gl: "de", q: `"{kw}" "Powered by Shopify"` },
  { lang: "fr", hl: "fr", gl: "fr", q: `"{kw}" "Powered by Shopify"` },
  { lang: "it", hl: "it", gl: "it", q: `"{kw}" "Powered by Shopify"` },
  { lang: "es", hl: "es", gl: "es", q: `"{kw}" "Powered by Shopify"` },
  { lang: "nl", hl: "nl", gl: "nl", q: `"{kw}" "Powered by Shopify"` },
  { lang: "pt", hl: "pt", gl: "pt", q: `"{kw}" "Powered by Shopify"` },
  { lang: "en", hl: "en", gl: "us", q: `"{kw}" inurl:/products/` },
];

function domainOf(url) {
  try {
    const u = new URL(url);
    return u.hostname.toLowerCase().replace(/^www\./, "");
  } catch {
    return null;
  }
}

function isLikelyShopifyDomain(domain) {
  if (!domain) return false;
  if (domain.endsWith(".myshopify.com")) return true;
  // Shopify is used on arbitrary TLDs — discovery.js returns everything
  // and shopify-validator.js confirms via HTTP headers + /products.json.
  return !/\.(gov|mil|edu)$/i.test(domain);
}

function buildKeywordVariants(fingerprint) {
  const variants = new Set();
  if (fingerprint.title_normalized) variants.add(fingerprint.title_normalized);
  for (const kw of fingerprint.keywords ?? []) variants.add(kw);
  // Pairs of keywords catch multi-word products like "magnetic eyelashes".
  const kws = fingerprint.keywords ?? [];
  for (let i = 0; i < kws.length; i++) {
    for (let j = i + 1; j < kws.length; j++) {
      variants.add(`${kws[i]} ${kws[j]}`);
    }
  }
  return [...variants].filter((v) => v && v.length >= 3).slice(0, 8);
}

async function serpApiSearch({ query, hl, gl }) {
  const result = await getJson({
    engine: "google",
    api_key: API_KEYS.serpApi,
    q: query,
    hl, gl,
    num: 20,
  });
  const organic = result?.organic_results ?? [];
  return organic
    .map((r) => ({ domain: domainOf(r.link), url: r.link, title: r.title }))
    .filter((r) => r.domain);
}

async function googleCseSearch({ query, hl, gl }) {
  const { apiKey, cx } = API_KEYS.googleCse;
  if (!apiKey || !cx) return [];
  const { data } = await axios.get("https://www.googleapis.com/customsearch/v1", {
    params: { key: apiKey, cx, q: query, hl, gl, num: 10 },
    timeout: 15_000,
  });
  return (data.items ?? [])
    .map((r) => ({ domain: domainOf(r.link), url: r.link, title: r.title }))
    .filter((r) => r.domain);
}

async function searchOne(tmpl, keyword, costTracker) {
  const query = tmpl.q.replace("{kw}", keyword);
  try {
    if (API_KEYS.serpApi && costTracker.usd < THRESHOLDS.maxCostUsd) {
      costTracker.usd += 0.005; // SerpAPI pay-per-search
      return await serpApiSearch({ query, hl: tmpl.hl, gl: tmpl.gl });
    }
    return await googleCseSearch({ query, hl: tmpl.hl, gl: tmpl.gl });
  } catch (err) {
    // Graceful degradation: CSE fallback on any SerpAPI error.
    try { return await googleCseSearch({ query, hl: tmpl.hl, gl: tmpl.gl }); }
    catch { return []; }
  }
}

async function loadSeedDataset() {
  // Reuse the existing Python skill dataset if present — this is a useful
  // cold-start for discovery, especially before the Supabase network-effect
  // cache warms up.
  try {
    const path = new URL("../../../data/shopify_sample_stores.json", import.meta.url);
    const { default: fs } = await import("node:fs/promises");
    const text = await fs.readFile(path, "utf8");
    const list = JSON.parse(text);
    return list.map((d) => ({ domain: d, url: `https://${d}`, title: null, source: "seed" }));
  } catch {
    return [];
  }
}

async function discoverCandidates(fingerprint, { onBatch } = {}) {
  const variants = buildKeywordVariants(fingerprint);
  const limit = pLimit(THRESHOLDS.serpApiConcurrency);
  const costTracker = { usd: 0 };
  const seen = new Map(); // domain → record with hit_count

  const merge = (batch) => {
    for (const item of batch) {
      if (!isLikelyShopifyDomain(item.domain)) continue;
      const existing = seen.get(item.domain);
      if (existing) {
        existing.hit_count += 1;
        existing.queries_matched.add(item._q);
      } else {
        seen.set(item.domain, {
          domain: item.domain,
          sample_url: item.url,
          sample_title: item.title,
          hit_count: 1,
          queries_matched: new Set([item._q]),
          source: item.source ?? "serp",
        });
      }
    }
    if (onBatch) onBatch({ total: seen.size, cost: costTracker.usd });
  };

  // 1. Seeded dataset (free, instant).
  const seed = await loadSeedDataset();
  merge(seed.map((x) => ({ ...x, _q: "seed" })));

  // 2. SerpAPI / CSE queries in parallel, capped by concurrency.
  const tasks = [];
  for (const kw of variants) {
    for (const tmpl of QUERY_TEMPLATES) {
      tasks.push(limit(async () => {
        if (seen.size >= THRESHOLDS.maxCandidateDomains) return;
        if (costTracker.usd >= THRESHOLDS.maxCostUsd) return;
        const q = `${tmpl.gl}::${tmpl.q.replace("{kw}", kw)}`;
        const results = await searchOne(tmpl, kw, costTracker);
        merge(results.map((r) => ({ ...r, _q: q })));
      }));
    }
  }
  await Promise.all(tasks);

  // Rank: domains that matched multiple queries / languages are more likely
  // to actually be reselling the product.
  return [...seen.values()]
    .map((x) => ({ ...x, queries_matched: [...x.queries_matched] }))
    .sort((a, b) => b.hit_count - a.hit_count)
    .slice(0, THRESHOLDS.maxCandidateDomains);
}

export { discoverCandidates, buildKeywordVariants, domainOf };
