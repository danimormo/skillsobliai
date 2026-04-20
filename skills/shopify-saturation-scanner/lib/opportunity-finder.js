// Identify BLUE_OCEAN markets: countries with established e-commerce
// demand, low current Shopify saturation for this product, and non-zero
// Google Trends interest for the product keyword.

import axios from "axios";
import { API_KEYS } from "../config/api-keys.js";
import { THRESHOLDS, ECOM_MARKET_POPULATION } from "../config/thresholds.js";
import { getJson } from "serpapi";

async function googleTrendsInterest(keyword, country) {
  if (!API_KEYS.serpApi) return null;
  try {
    const res = await getJson({
      engine: "google_trends",
      api_key: API_KEYS.serpApi,
      q: keyword,
      geo: country,
      data_type: "TIMESERIES",
    });
    const series = res?.interest_over_time?.timeline_data ?? [];
    if (!series.length) return 0;
    const last12 = series.slice(-12);
    const avg = last12.reduce((a, p) => a + (p.values?.[0]?.extracted_value ?? 0), 0) / last12.length;
    return Math.round(avg);
  } catch {
    return null;
  }
}

function findPotentialMarkets({ marketRows, fingerprint }) {
  const seen = new Map(marketRows.map((r) => [r.country, r]));
  const candidates = THRESHOLDS.ecommerceMarkets.filter((cc) => {
    const row = seen.get(cc);
    if (!row) return true; // zero stores found → definitely under-served
    return row.store_count < THRESHOLDS.blueOceanMaxStoresPerCountry;
  });
  return candidates;
}

async function enrichWithTrends(countries, fingerprint) {
  const keyword = (fingerprint.keywords?.[0] ?? fingerprint.title_normalized ?? "").slice(0, 60);
  if (!keyword) return countries.map((c) => ({ country: c, trend: null }));

  const rows = await Promise.all(countries.map(async (c) => {
    const trend = await googleTrendsInterest(keyword, c);
    return { country: c, trend };
  }));

  return rows
    .filter((r) => r.trend === null || r.trend >= THRESHOLDS.blueOceanMinGoogleTrends)
    .sort((a, b) => (b.trend ?? 0) - (a.trend ?? 0));
}

function buildRecommendation({ saturation_zone, marketRows, blueOceans, fingerprint }) {
  const topSaturated = marketRows
    .filter((r) => r.saturation_level === "red")
    .map((r) => r.country)
    .slice(0, 3);
  const opportunities = blueOceans.map((b) => b.country).slice(0, 5);

  if (saturation_zone === "green") {
    return `Prodotto poco diffuso su Shopify (<100 store totali). Il mercato è ancora aperto; entra ora su ${opportunities.slice(0, 3).join(", ") || "US/UK/DE"} prima che la concorrenza saturi i canali ads.`;
  }
  if (saturation_zone === "yellow") {
    const sat = topSaturated.length ? `${topSaturated.join("/")} sono già competitivi` : "competizione in crescita";
    return `Saturazione moderata: ${sat}. Opportunità reale in ${opportunities.slice(0, 4).join(", ") || "mercati non-anglofoni"} — differenzia con angolo creativo locale.`;
  }
  return `Mercato ${topSaturated.join("/")} saturo (red zone). Opportunità residua in ${opportunities.slice(0, 4).join(", ") || "DACH/Sud Europa/Nord Europa"}; richiede creative localizzate e prezzo competitivo.`;
}

async function findOpportunities({ marketRows, fingerprint, saturation_zone }) {
  const candidates = findPotentialMarkets({ marketRows, fingerprint });
  const withTrends = await enrichWithTrends(candidates, fingerprint);

  const enriched = withTrends.map((row) => {
    const existing = marketRows.find((r) => r.country === row.country);
    return {
      country: row.country,
      store_count: existing?.store_count ?? 0,
      saturation_level: "green",
      opportunity_flag: "BLUE_OCEAN",
      google_trends_interest: row.trend,
      population_millions: ECOM_MARKET_POPULATION[row.country]
        ? Math.round(ECOM_MARKET_POPULATION[row.country] / 1e6)
        : null,
    };
  });

  const recommendation = buildRecommendation({
    saturation_zone, marketRows, blueOceans: enriched, fingerprint,
  });

  return {
    potential_markets: enriched.map((e) => e.country),
    blue_ocean_details: enriched,
    recommendation,
  };
}

export { findOpportunities, googleTrendsInterest };
