// Determine the primary geographic market for a confirmed Shopify store.
// Combines multiple signals with weighted confidence:
//   - /cart.js currency           (strong)
//   - /meta.json shop country     (strong, when exposed)
//   - TLD                         (medium)
//   - Site language (franc)       (medium)
//   - Shipping info in footer     (weak)

import axios from "axios";
import { franc } from "franc";
import * as cheerio from "cheerio";
import { API_KEYS } from "../config/api-keys.js";

const http = axios.create({
  timeout: 8_000,
  headers: { "User-Agent": API_KEYS.userAgent },
  validateStatus: () => true,
});

const CURRENCY_TO_COUNTRY = {
  USD: "US", EUR: "EU", GBP: "GB", CAD: "CA", AUD: "AU", NZD: "NZ",
  CHF: "CH", SEK: "SE", NOK: "NO", DKK: "DK", PLN: "PL", CZK: "CZ",
  JPY: "JP", SGD: "SG", HKD: "HK", AED: "AE", BRL: "BR", MXN: "MX",
  INR: "IN", ZAR: "ZA",
};

const TLD_TO_COUNTRY = {
  "de": "DE", "it": "IT", "fr": "FR", "es": "ES", "nl": "NL", "pt": "PT",
  "co.uk": "GB", "uk": "GB", "ca": "CA", "au": "AU", "nz": "NZ",
  "se": "SE", "no": "NO", "dk": "DK", "fi": "FI", "ch": "CH", "at": "AT",
  "be": "BE", "ie": "IE", "pl": "PL", "cz": "CZ", "mx": "MX", "br": "BR",
  "jp": "JP", "sg": "SG",
};

const LANG_TO_COUNTRY = {
  eng: "US", deu: "DE", ita: "IT", fra: "FR", spa: "ES",
  nld: "NL", por: "PT", swe: "SE", nor: "NO", dan: "DK",
  fin: "FI", pol: "PL", ces: "CZ", jpn: "JP",
};

function tldOf(domain) {
  const parts = domain.split(".");
  if (parts.length < 2) return null;
  const last2 = parts.slice(-2).join(".");
  if (TLD_TO_COUNTRY[last2]) return last2;
  return parts[parts.length - 1];
}

async function currencyFromCart(domain) {
  const res = await http.get(`https://${domain}/cart.js`);
  if (res.status !== 200) return null;
  return res.data?.currency ?? null;
}

async function countryFromMeta(domain) {
  // Some stores expose /meta.json with shop metadata.
  const res = await http.get(`https://${domain}/meta.json`);
  if (res.status !== 200) return null;
  return res.data?.country ?? res.data?.shop?.country ?? null;
}

async function langFromHomepage(domain) {
  const res = await http.get(`https://${domain}/`, { responseType: "text" });
  if (res.status !== 200) return { lang: null, shipping: [] };
  const html = typeof res.data === "string" ? res.data : "";
  const $ = cheerio.load(html);
  const textSample = ($("body").text() || "").slice(0, 5000);
  const langHint = $("html").attr("lang");
  const lang = langHint ? langHint.toLowerCase().slice(0, 2) : null;
  const detected = textSample.length > 200 ? franc(textSample, { minLength: 80 }) : null;

  const shipping = [];
  $("footer, [class*=shipping], [class*=country]").each((_, el) => {
    const t = $(el).text();
    for (const cc of Object.values(TLD_TO_COUNTRY)) {
      if (new RegExp(`\\b${cc}\\b`).test(t)) shipping.push(cc);
    }
  });

  return { lang, detected, shipping: [...new Set(shipping)] };
}

async function locateStore(storeMatch) {
  const { domain } = storeMatch;
  const signals = {};
  let confidence = 0;
  let primary = null;

  // Run the three independent probes in parallel.
  const [currency, metaCountry, homepage] = await Promise.all([
    currencyFromCart(domain).catch(() => null),
    countryFromMeta(domain).catch(() => null),
    langFromHomepage(domain).catch(() => ({ lang: null, shipping: [] })),
  ]);

  if (currency) {
    signals.currency = currency;
    const mapped = CURRENCY_TO_COUNTRY[currency];
    if (mapped && mapped !== "EU") {
      primary = mapped;
      confidence += 40;
    } else if (mapped === "EU") {
      // Need TLD/lang to disambiguate EUR.
      confidence += 10;
    }
  }

  if (metaCountry) {
    signals.meta_country = metaCountry;
    primary = metaCountry.toUpperCase();
    confidence += 40;
  }

  const tld = tldOf(domain);
  if (tld && TLD_TO_COUNTRY[tld]) {
    signals.tld = tld;
    const c = TLD_TO_COUNTRY[tld];
    if (!primary) primary = c;
    confidence += 25;
  }

  const langKey = homepage.detected ?? null;
  if (langKey && LANG_TO_COUNTRY[langKey]) {
    signals.language = langKey;
    if (!primary) primary = LANG_TO_COUNTRY[langKey];
    confidence += 15;
  } else if (homepage.lang && LANG_TO_COUNTRY[`${homepage.lang}0`]) {
    // html lang attr is less reliable; minimal bump.
    confidence += 5;
  }

  if (homepage.shipping?.length === 1) {
    signals.shipping_hint = homepage.shipping[0];
    if (!primary) primary = homepage.shipping[0];
    confidence += 10;
  }

  // Default fallback — assume US when absolutely no signal resolved, but
  // set a very low confidence so callers can discount it.
  if (!primary) {
    primary = "US";
    confidence = Math.max(confidence, 5);
  }

  return {
    ...storeMatch,
    primary_market: primary,
    geo_confidence: Math.min(100, confidence),
    signals,
  };
}

export { locateStore, currencyFromCart, countryFromMeta };
