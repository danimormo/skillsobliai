// Unit + integration tests for the saturation scanner.
//
// Run:  node --test tests/saturation.test.js
// Live mode (hits real SerpAPI): SATURATION_LIVE=1 node --test tests/saturation.test.js
//
// The live suite is opt-in so CI doesn't consume SerpAPI quota on every push.

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

import {
  normalizeTitle, extractKeywords, isGenericProduct, fingerprintCacheKey,
} from "../lib/fingerprint.js";
import { titleSimilarity, hammingHex } from "../lib/shopify-validator.js";
import { scoreSaturation, marketBreakdown, zoneFor } from "../lib/saturation-scorer.js";
import { buildKeywordVariants, domainOf } from "../lib/discovery.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FIXTURES = JSON.parse(readFileSync(path.join(__dirname, "fixtures/products.json"), "utf8"));

// ── fingerprint.js ────────────────────────────────────────────────────────

test("normalizeTitle strips brand/stopwords and punctuation", () => {
  assert.equal(
    normalizeTitle("The Premium Magnetic Eyelashes & Eyeliner Kit (Official Store)"),
    "magnetic eyelashes eyeliner kit",
  );
});

test("extractKeywords picks the highest-signal tokens", () => {
  const tokens = extractKeywords("magnetic eyelashes eyeliner kit");
  assert.ok(tokens.includes("eyelashes"));
  assert.ok(tokens.length <= 4);
});

test("isGenericProduct flags <=2-token titles", () => {
  assert.equal(isGenericProduct({ title_normalized: "white tshirt" }), true);
  assert.equal(isGenericProduct({ title_normalized: "magnetic eyelashes eyeliner kit" }), false);
});

test("fingerprintCacheKey prefers image hash, falls back to title", () => {
  assert.equal(
    fingerprintCacheKey({ image_hash: "phash:abc", title_normalized: "x" }),
    "fp:phash:abc",
  );
  assert.equal(
    fingerprintCacheKey({ image_hash: null, title_normalized: "magnetic eyelashes" }),
    "fp:title:magnetic eyelashes",
  );
});

// ── discovery.js ──────────────────────────────────────────────────────────

test("domainOf extracts hostname without www", () => {
  assert.equal(domainOf("https://www.Foo.com/products/x"), "foo.com");
  assert.equal(domainOf("https://xyz.myshopify.com/"), "xyz.myshopify.com");
  assert.equal(domainOf("not-a-url"), null);
});

test("buildKeywordVariants emits pairs and single keywords", () => {
  const fp = {
    title_normalized: "magnetic eyelashes eyeliner kit",
    keywords: ["magnetic", "eyelashes", "eyeliner", "kit"],
  };
  const vs = buildKeywordVariants(fp);
  assert.ok(vs.includes("magnetic"));
  assert.ok(vs.includes("eyelashes"));
  assert.ok(vs.some((v) => v.includes("magnetic") && v.includes("eyelashes")));
});

// ── shopify-validator.js ──────────────────────────────────────────────────

test("titleSimilarity is near-1 for identical, low for unrelated", () => {
  const s = titleSimilarity("Magnetic Eyelashes Kit", "magnetic eyelashes kit");
  assert.ok(s >= 0.95);
  const u = titleSimilarity("Magnetic Eyelashes", "Wireless Bluetooth Speaker");
  assert.ok(u < 0.25);
});

test("titleSimilarity handles translated/paraphrased titles via token overlap", () => {
  const s = titleSimilarity("Magnetic Eyelashes Kit", "Kit Ciglia Finte Magnetiche");
  assert.ok(s < 0.5, "pure title sim on different language should be low without translation");
});

test("hammingHex returns 0 on identical hashes", () => {
  assert.equal(hammingHex("ffffffff", "ffffffff"), 0);
  assert.equal(hammingHex("ffffffff", "00000000"), 32);
});

// ── saturation-scorer.js ──────────────────────────────────────────────────

test("zoneFor obeys configured thresholds", () => {
  assert.equal(zoneFor(0), "green");
  assert.equal(zoneFor(50), "green");
  assert.equal(zoneFor(200), "yellow");
  assert.equal(zoneFor(900), "red");
});

test("scoreSaturation produces 0-100 score with zone and components", () => {
  const stores = [
    { primary_market: "US", ads_active: true,  matched_product: { price: 29.9, created_at: "2024-01-01" } },
    { primary_market: "US", ads_active: true,  matched_product: { price: 34.9, created_at: "2023-10-01" } },
    { primary_market: "GB", ads_active: false, matched_product: { price: 39.9, created_at: "2024-05-01" } },
    { primary_market: "DE", ads_active: true,  matched_product: { price: 29.9, created_at: "2024-06-01" } },
  ];
  const res = scoreSaturation({ confirmedStores: stores, adsActiveCount: 3 });
  assert.ok(res.saturation_score >= 0 && res.saturation_score <= 100);
  assert.ok(["green", "yellow", "red"].includes(res.saturation_zone));
  assert.ok(res.components.total_stores >= 0);
  assert.equal(res.components.market_concentration <= 100, true);
});

test("marketBreakdown groups by country and sorts desc", () => {
  const stores = [
    { primary_market: "DE", matched_product: { price: "20", product_url: "https://a.de/p/1" }, domain: "a.de", match_confidence: 0.9 },
    { primary_market: "US", matched_product: { price: "25", product_url: "https://b.us/p/1" }, domain: "b.us", match_confidence: 0.8 },
    { primary_market: "US", matched_product: { price: "27", product_url: "https://c.us/p/1" }, domain: "c.us", match_confidence: 0.88 },
  ];
  const rows = marketBreakdown(stores);
  assert.equal(rows[0].country, "US");
  assert.equal(rows[0].store_count, 2);
  assert.equal(rows[1].country, "DE");
  assert.ok(rows[0].avg_price_usd >= 25);
});

// ── fixtures sanity ───────────────────────────────────────────────────────

test("all 5 fixtures parse and expose the required contract", () => {
  assert.equal(FIXTURES.length, 5);
  for (const f of FIXTURES) {
    assert.ok(f.name && f.url && f.expected);
    assert.ok(Array.isArray(f.expected.keywords_contains_any));
  }
});

// ── live integration (opt-in) ─────────────────────────────────────────────

if (process.env.SATURATION_LIVE === "1") {
  const { runScan } = await import("../index.js");

  for (const fixture of FIXTURES) {
    test(`live: ${fixture.name} returns a valid result shape`, async () => {
      const res = await runScan({ url: fixture.url, userId: "test" });
      assert.ok(res.product_fingerprint);
      assert.ok(["green", "yellow", "red"].includes(res.saturation_zone));
      assert.ok(Array.isArray(res.markets));
      assert.ok(Array.isArray(res.potential_markets));
      if (fixture.expected.expected_potential_markets_min) {
        assert.ok(res.potential_markets.length >= fixture.expected.expected_potential_markets_min);
      }
      const kws = new Set((res.product_fingerprint.keywords ?? []).map((k) => k.toLowerCase()));
      const hasAny = fixture.expected.keywords_contains_any.some((k) => kws.has(k.toLowerCase()));
      assert.ok(hasAny, `expected one of ${JSON.stringify(fixture.expected.keywords_contains_any)} in keywords`);
    }, { timeout: 4 * 60 * 1000 });
  }
}
