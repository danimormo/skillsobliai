// Product fingerprinting: URL-mode OR image-mode → normalized fingerprint
// used by discovery.js to search the web and by shopify-validator.js to match
// candidate product titles/images.

import axios from "axios";
import * as cheerio from "cheerio";
import sharp from "sharp";
import { imageHash } from "image-hash";
import { getJson } from "serpapi";
import { API_KEYS } from "../config/api-keys.js";

const STOPWORDS = new Set([
  "the", "a", "an", "and", "or", "for", "with", "of", "to", "in", "on",
  "new", "hot", "sale", "premium", "official", "original", "best",
  "buy", "shop", "store", "online", "free", "shipping", "limited",
]);

const BRANDY_WORDS = /\b(tm|®|©|inc|llc|ltd|co\.?|store|shop|official|by [a-z0-9]+)\b/gi;

function pHashFromBuffer(buffer) {
  return new Promise((resolve, reject) => {
    imageHash({ data: buffer }, 16, true, (err, hash) => {
      if (err) return reject(err);
      resolve(hash);
    });
  });
}

function normalizeTitle(raw) {
  if (!raw) return "";
  return raw
    .toLowerCase()
    .replace(BRANDY_WORDS, " ")
    .replace(/[^a-z0-9\s]/g, " ")
    .split(/\s+/)
    .filter((t) => t && !STOPWORDS.has(t))
    .join(" ")
    .trim();
}

function extractKeywords(normalized) {
  const tokens = normalized.split(/\s+/).filter(Boolean);
  // Keep the 4 most "content-bearing" tokens (longest first).
  return [...new Set(tokens)]
    .sort((a, b) => b.length - a.length)
    .slice(0, 4);
}

function isShopifyUrl(url) {
  return /\/products\/[\w-]+/i.test(url) || /\.myshopify\.com/i.test(url);
}

async function downloadImage(url) {
  const res = await axios.get(url, {
    responseType: "arraybuffer",
    headers: { "User-Agent": API_KEYS.userAgent },
    timeout: 15_000,
    maxContentLength: 15 * 1024 * 1024,
  });
  const buf = Buffer.from(res.data);
  // Normalize to JPEG 512px so pHash is deterministic across variants.
  const normalized = await sharp(buf)
    .resize(512, 512, { fit: "inside", withoutEnlargement: true })
    .jpeg({ quality: 85 })
    .toBuffer();
  return { raw: buf, normalized };
}

async function fingerprintFromUrl(url) {
  const { data: html } = await axios.get(url, {
    headers: { "User-Agent": API_KEYS.userAgent },
    timeout: 15_000,
    maxRedirects: 5,
  });
  const $ = cheerio.load(html);

  const title =
    $('meta[property="og:title"]').attr("content") ??
    $("title").first().text() ??
    "";
  const metaDesc = $('meta[name="description"]').attr("content") ?? "";
  const ogImage = $('meta[property="og:image"]').attr("content") ?? null;

  let jsonLd = null;
  $('script[type="application/ld+json"]').each((_, el) => {
    if (jsonLd) return;
    try {
      const parsed = JSON.parse($(el).text());
      const items = Array.isArray(parsed) ? parsed : [parsed];
      jsonLd = items.find((x) => x?.["@type"] === "Product") ?? null;
    } catch { /* swallow malformed JSON-LD */ }
  });

  // If Shopify, the /products/slug.json endpoint gives clean structured data.
  let shopifyJson = null;
  if (isShopifyUrl(url)) {
    try {
      const jsonUrl = url.split("?")[0].replace(/\/$/, "") + ".json";
      const { data } = await axios.get(jsonUrl, {
        headers: { "User-Agent": API_KEYS.userAgent },
        timeout: 10_000,
      });
      shopifyJson = data?.product ?? null;
    } catch { /* not shopify / blocked — keep html-derived data */ }
  }

  const resolvedTitle = shopifyJson?.title ?? jsonLd?.name ?? title;
  const resolvedImage =
    shopifyJson?.images?.[0]?.src ??
    (Array.isArray(jsonLd?.image) ? jsonLd.image[0] : jsonLd?.image) ??
    ogImage;

  let imageData = null;
  if (resolvedImage) {
    try { imageData = await downloadImage(resolvedImage); }
    catch { /* ignore — fingerprint still usable via title */ }
  }

  const normalized = normalizeTitle(resolvedTitle);
  return {
    source_url: url,
    is_shopify: !!shopifyJson || isShopifyUrl(url),
    raw_title: resolvedTitle,
    title_normalized: normalized,
    keywords: extractKeywords(normalized),
    description: shopifyJson?.body_html
      ? cheerio.load(shopifyJson.body_html).text().trim().slice(0, 400)
      : metaDesc.slice(0, 400),
    image_url: resolvedImage,
    image_hash: imageData ? `phash:${await pHashFromBuffer(imageData.normalized)}` : null,
    price: shopifyJson?.variants?.[0]?.price ?? jsonLd?.offers?.price ?? null,
    variants_count: shopifyJson?.variants?.length ?? null,
    identified_by: "url",
  };
}

async function fingerprintFromImage(imageBuffer) {
  if (!imageBuffer || imageBuffer.length < 4_000) {
    throw new Error("Image too small or missing — request an HD upload (>200kb recommended)");
  }
  const meta = await sharp(imageBuffer).metadata();
  if ((meta.width ?? 0) < 256 || (meta.height ?? 0) < 256) {
    // Low-res → continue but flag; caller decides if to proceed.
    // (We still compute the hash; discovery caller will lower confidence.)
  }

  const normalizedBuf = await sharp(imageBuffer)
    .resize(512, 512, { fit: "inside", withoutEnlargement: true })
    .jpeg({ quality: 85 })
    .toBuffer();

  const hash = await pHashFromBuffer(normalizedBuf);

  // Reverse image search via SerpAPI Google Lens → extract candidate
  // titles / shopping listings that describe what the product is.
  let lensResult = null;
  if (API_KEYS.serpApi) {
    // SerpAPI Google Lens expects a publicly reachable image URL. In a
    // real deployment the API caller uploads the image to Supabase
    // Storage first and passes the signed URL in; we accept a URL here
    // directly via the orchestration layer (see index.js).
    lensResult = null; // performed by caller, wired via fingerprintFromLensResult
  }

  const titleGuess = ""; // filled when caller merges Lens data
  return {
    source_url: null,
    is_shopify: false,
    raw_title: titleGuess,
    title_normalized: normalizeTitle(titleGuess),
    keywords: [],
    description: "",
    image_url: null,
    image_hash: `phash:${hash}`,
    price: null,
    variants_count: null,
    identified_by: "image",
    low_resolution: (meta.width ?? 0) < 512,
  };
}

// Enrich an image-mode fingerprint with Google Lens output (descriptive
// labels + shopping listings). Call this from index.js after the image
// has been uploaded to a public URL (Supabase storage signed URL works).
async function enrichWithGoogleLens(fingerprint, publicImageUrl) {
  if (!API_KEYS.serpApi) return fingerprint;
  const lens = await getJson({
    engine: "google_lens",
    api_key: API_KEYS.serpApi,
    url: publicImageUrl,
  });

  const listings = lens?.visual_matches ?? [];
  // Majority-vote the title from top 10 shopping listings.
  const candidateTitles = listings.slice(0, 10).map((x) => x.title).filter(Boolean);
  const bestTitle = candidateTitles
    .map((t) => ({ t, n: normalizeTitle(t) }))
    .sort((a, b) => b.n.length - a.n.length)[0]?.t ?? "";
  const normalized = normalizeTitle(bestTitle);

  return {
    ...fingerprint,
    raw_title: bestTitle,
    title_normalized: normalized,
    keywords: extractKeywords(normalized),
    identified_by: "hybrid",
    lens_candidates: listings.slice(0, 25).map((m) => ({
      title: m.title, link: m.link, source: m.source, price: m.price?.value,
    })),
  };
}

function fingerprintCacheKey(fp) {
  // Stable key across call sites: image hash is the strongest dedup signal,
  // then normalized title.
  if (fp.image_hash) return `fp:${fp.image_hash}`;
  return `fp:title:${fp.title_normalized}`;
}

function isGenericProduct(fp) {
  const tokens = fp.title_normalized.split(/\s+/).filter(Boolean);
  return tokens.length <= 2;
}

export {
  fingerprintFromUrl,
  fingerprintFromImage,
  enrichWithGoogleLens,
  normalizeTitle,
  extractKeywords,
  fingerprintCacheKey,
  isGenericProduct,
  isShopifyUrl,
};
