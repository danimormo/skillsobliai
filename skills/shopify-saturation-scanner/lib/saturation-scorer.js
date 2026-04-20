// Saturation score (0-100) + zone classification for a scan result.
// Formula (matches prompt):
//   score = totalStores*0.40 + marketConcentration*0.25
//         + adsActiveRatio*0.20 + ageFactor*0.15
// Each component is normalized to 0-100 before weighting.

import { THRESHOLDS } from "../config/thresholds.js";

function clamp(v, lo, hi) { return Math.min(hi, Math.max(lo, v)); }

function normalizeTotalStores(n) {
  // Log-ish curve: 0 → 0, 100 → 45, 500 → 85, 1000+ → 100.
  if (n <= 0) return 0;
  return clamp(Math.round(100 * Math.log10(n + 1) / 3), 0, 100);
}

function normalizeConcentration(stores) {
  if (!stores.length) return 0;
  const byCountry = new Map();
  for (const s of stores) byCountry.set(s.primary_market, (byCountry.get(s.primary_market) ?? 0) + 1);
  const sorted = [...byCountry.values()].sort((a, b) => b - a);
  const top3 = sorted.slice(0, 3).reduce((a, b) => a + b, 0);
  return Math.round((top3 / stores.length) * 100);
}

function normalizeAdsRatio(ratio) {
  return clamp(Math.round(ratio * 100), 0, 100);
}

function normalizeAge(stores) {
  // Use median created_at of matched products. Younger = less saturated.
  const ages = stores
    .map((s) => s.matched_product?.created_at)
    .filter(Boolean)
    .map((d) => (Date.now() - new Date(d).getTime()) / (1000 * 86400));
  if (!ages.length) return 50;
  ages.sort((a, b) => a - b);
  const medianDays = ages[Math.floor(ages.length / 2)];
  // 30d → 10, 180d → 50, 365d → 80, 730d+ → 100.
  return clamp(Math.round((medianDays / 730) * 100), 0, 100);
}

function zoneFor(totalStores) {
  const { greenMax, yellowMax } = THRESHOLDS.zones;
  if (totalStores < greenMax) return "green";
  if (totalStores <= yellowMax) return "yellow";
  return "red";
}

function scoreSaturation({ confirmedStores, adsActiveCount }) {
  const n = confirmedStores.length;
  const adsRatio = n > 0 ? (adsActiveCount ?? 0) / n : 0;

  const components = {
    total_stores: normalizeTotalStores(n),
    market_concentration: normalizeConcentration(confirmedStores),
    ads_active_ratio: normalizeAdsRatio(adsRatio),
    age_factor: normalizeAge(confirmedStores),
  };

  const { weights } = THRESHOLDS;
  const raw =
    components.total_stores * weights.totalStores +
    components.market_concentration * weights.marketConcentration +
    components.ads_active_ratio * weights.adsActiveRatio +
    components.age_factor * weights.ageFactor;

  const saturation_score = Math.round(clamp(raw, 0, 100));
  const saturation_zone = zoneFor(n);

  return { saturation_score, saturation_zone, components };
}

function marketBreakdown(confirmedStores) {
  const byCountry = new Map();
  for (const s of confirmedStores) {
    const key = s.primary_market ?? "UNK";
    if (!byCountry.has(key)) byCountry.set(key, { country: key, stores: [] });
    byCountry.get(key).stores.push(s);
  }

  const rows = [];
  for (const { country, stores } of byCountry.values()) {
    const prices = stores
      .map((s) => Number(s.matched_product?.price))
      .filter((v) => Number.isFinite(v) && v > 0);
    const avg_price_usd = prices.length
      ? Number((prices.reduce((a, b) => a + b, 0) / prices.length).toFixed(2))
      : null;

    rows.push({
      country,
      store_count: stores.length,
      saturation_level: zoneFor(stores.length),
      avg_price_usd,
      top_stores: stores
        .slice(0, 5)
        .map((s) => ({
          domain: s.domain,
          product_url: s.matched_product?.product_url ?? null,
          match_confidence: s.match_confidence,
          ads_active: !!s.ads_active,
        })),
    });
  }

  return rows.sort((a, b) => b.store_count - a.store_count);
}

export { scoreSaturation, marketBreakdown, zoneFor };
