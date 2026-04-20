// Configurable thresholds for the saturation scanner.
// Tune these from env vars when iterating on scan quality/cost in production.

export const THRESHOLDS = {
  // Scan budget (hard ceilings).
  maxScanDurationMs: Number(process.env.SCAN_MAX_DURATION_MS ?? 180_000), // 3 min
  maxCandidateDomains: Number(process.env.SCAN_MAX_CANDIDATES ?? 1500),
  maxConfirmedStores: Number(process.env.SCAN_MAX_CONFIRMED ?? 1200),
  maxCostUsd: Number(process.env.SCAN_MAX_COST_USD ?? 0.15),

  // Concurrency.
  serpApiConcurrency: 4,
  storeValidationConcurrency: 20,
  geoLocatorConcurrency: 15,

  // Similarity matching.
  titleSimilarityMin: 0.72,          // normalized Levenshtein ratio
  titleSimilarityGeneric: 0.90,      // tighter threshold for generic products
  imageHashMaxHamming: 10,           // pHash distance for image match
  genericProductMaxTokens: 2,        // e.g. "white t-shirt" → generic

  // Saturation scoring weights (sum = 1.0).
  weights: {
    totalStores: 0.40,
    marketConcentration: 0.25,
    adsActiveRatio: 0.20,
    ageFactor: 0.15,
  },

  // Zone thresholds on raw total_shopify_stores.
  zones: {
    greenMax: 100,
    yellowMax: 500,
  },

  // Blue-ocean detection.
  blueOceanMaxStoresPerCountry: 10,
  blueOceanMinGoogleTrends: 40,      // 0-100 scale
  ecommerceMarkets: ["US", "GB", "DE", "FR", "IT", "ES", "AU", "CA", "NL", "SE", "CH", "AT", "BE", "IE", "DK", "NO", "FI", "PT"],

  // Early-stop: if confirmed store count exceeds this during discovery,
  // stop broad discovery and jump to geo-location (caller still sees streaming updates).
  earlyStopConfirmed: 350,

  // Cache TTL.
  fingerprintTtlSec: 24 * 3600,
  storeLookupTtlSec: 24 * 3600,
};

export const ECOM_MARKET_POPULATION = {
  US: 332e6, GB: 67e6, DE: 84e6, FR: 67e6, IT: 59e6, ES: 47e6,
  AU: 26e6, CA: 40e6, NL: 17e6, SE: 10e6, CH: 8.7e6, AT: 9e6,
  BE: 11.6e6, IE: 5.1e6, DK: 5.9e6, NO: 5.5e6, FI: 5.5e6, PT: 10.3e6,
};
