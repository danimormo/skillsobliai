// Centralized env-var loading. Fails fast at startup with a clear error.

function req(name, { optional = false } = {}) {
  const v = process.env[name];
  if (!v && !optional) {
    throw new Error(`[shopify-saturation-scanner] missing required env var: ${name}`);
  }
  return v ?? null;
}

export const API_KEYS = {
  // Primary reverse image search + Google SERP.
  serpApi: req("SERPAPI_API_KEY", { optional: true }),

  // Fallback when SerpAPI fails / budget exceeded.
  googleCse: {
    apiKey: req("GOOGLE_CSE_API_KEY", { optional: true }),
    cx: req("GOOGLE_CSE_CX", { optional: true }),
  },

  // Meta Ads Library cross-reference (via ScrapeCreators — same as existing stack).
  scrapeCreators: req("SCRAPECREATORS_API_KEY", { optional: true }),

  // Supabase: shared fingerprint + store cache (network-effect enabled).
  supabase: {
    url: req("SUPABASE_URL", { optional: true }),
    serviceKey: req("SUPABASE_SERVICE_KEY", { optional: true }),
  },

  // Redis / BullMQ queue.
  redisUrl: req("REDIS_URL", { optional: true }) ?? "redis://localhost:6379",

  // Telegram scan-completion notifications.
  telegram: {
    botToken: req("TELEGRAM_BOT_TOKEN", { optional: true }),
    defaultChatId: req("TELEGRAM_DEFAULT_CHAT_ID", { optional: true }),
  },

  // Realistic UA for page fetches (respects robots.txt, no bypass).
  userAgent: process.env.SCANNER_USER_AGENT
    ?? "Mozilla/5.0 (compatible; ObliaiSaturationBot/1.0; +https://obliai.com/bot)",
};

export function assertRequiredForLiveScan() {
  if (!API_KEYS.serpApi && !API_KEYS.googleCse.apiKey) {
    throw new Error("Need at least one of SERPAPI_API_KEY or GOOGLE_CSE_API_KEY for live scans");
  }
}
