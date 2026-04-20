// Meta Ads Library cross-reference — detects whether a confirmed store is
// actively running ads for the product. Uses ScrapeCreators (same provider
// already wired in the parent repo) when the key is present; otherwise the
// check is skipped and all stores default to ads_active=false.

import axios from "axios";
import pLimit from "p-limit";
import { API_KEYS } from "../config/api-keys.js";

const SCRAPECREATORS_URL = "https://api.scrapecreators.com/v1/facebook/ads/search";

async function isStoreAdvertising(domain, keyword) {
  if (!API_KEYS.scrapeCreators) return { ads_active: false, checked: false };
  try {
    const { data } = await axios.get(SCRAPECREATORS_URL, {
      headers: { "x-api-key": API_KEYS.scrapeCreators },
      params: { query: domain, status: "ACTIVE", limit: 3 },
      timeout: 8_000,
    });
    const ads = data?.ads ?? data?.results ?? [];
    const hasActive = ads.some((ad) => {
      const text = `${ad.ad_creative_body ?? ""} ${ad.page_name ?? ""}`.toLowerCase();
      return text.includes(domain.split(".")[0]) || (keyword && text.includes(keyword));
    });
    return { ads_active: hasActive, checked: true, ad_count: ads.length };
  } catch {
    return { ads_active: false, checked: false, error: true };
  }
}

async function enrichWithAdsStatus(stores, fingerprint, { concurrency = 10 } = {}) {
  const keyword = (fingerprint.keywords?.[0] ?? "").toLowerCase();
  const limit = pLimit(concurrency);
  return Promise.all(stores.map((s) => limit(async () => {
    const status = await isStoreAdvertising(s.domain, keyword);
    return { ...s, ads_active: status.ads_active, ads_checked: status.checked };
  })));
}

export { enrichWithAdsStatus, isStoreAdvertising };
