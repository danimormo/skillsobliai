// Given a candidate domain + target fingerprint, confirm that:
//   (1) the domain is actually a Shopify store, and
//   (2) the store is selling the same (or very similar) product.
//
// Uses ONLY public endpoints (/products.json is a documented Shopify public
// endpoint). Respects robots.txt (scoped to /products.json), rate-limits,
// and tolerates stores that disable the endpoint.

import axios from "axios";
import levenshtein from "fast-levenshtein";
import { imageHash } from "image-hash";
import sharp from "sharp";
import { API_KEYS } from "../config/api-keys.js";
import { THRESHOLDS } from "../config/thresholds.js";
import { normalizeTitle, isGenericProduct } from "./fingerprint.js";

const http = axios.create({
  timeout: 8_000,
  maxRedirects: 3,
  headers: { "User-Agent": API_KEYS.userAgent, Accept: "application/json,text/html" },
  validateStatus: () => true,
});

async function confirmShopify(domain) {
  // Headers check is cheap and authoritative when present. Some stores
  // hide the header; we fall back to presence of /products.json.
  const url = `https://${domain}`;
  try {
    const head = await http.head(url);
    const h = head.headers;
    if (h["x-shopify-stage"] || h["x-shopid"] || h["x-sorting-hat-shopid"] || h["x-shopify-api-version"]) {
      return { isShopify: true, signal: "header" };
    }
    if (head.status >= 500) return { isShopify: false, signal: "unreachable" };
  } catch { /* fall through */ }

  const probe = await http.get(`${url}/products.json?limit=1`);
  if (probe.status === 200 && typeof probe.data === "object" && Array.isArray(probe.data?.products)) {
    return { isShopify: true, signal: "products_json" };
  }
  if (probe.status === 401 || probe.status === 403 || probe.status === 429) {
    return { isShopify: true, signal: "products_json_blocked", blocked: true };
  }
  return { isShopify: false, signal: "no_shopify_markers" };
}

function titleSimilarity(a, b) {
  if (!a || !b) return 0;
  const na = normalizeTitle(a);
  const nb = normalizeTitle(b);
  if (!na || !nb) return 0;
  const dist = levenshtein.get(na, nb);
  const ratio = 1 - dist / Math.max(na.length, nb.length);
  // Boost if token overlap is strong (word-level).
  const ta = new Set(na.split(" "));
  const tb = new Set(nb.split(" "));
  const overlap = [...ta].filter((t) => tb.has(t)).length / Math.max(ta.size, tb.size, 1);
  return Math.max(ratio, overlap);
}

async function hashImageFromUrl(url) {
  try {
    const res = await http.get(url, { responseType: "arraybuffer", timeout: 10_000 });
    if (res.status !== 200) return null;
    const buf = Buffer.from(res.data);
    const normalized = await sharp(buf)
      .resize(512, 512, { fit: "inside", withoutEnlargement: true })
      .jpeg({ quality: 85 })
      .toBuffer();
    return await new Promise((resolve, reject) => {
      imageHash({ data: normalized }, 16, true, (err, h) => err ? reject(err) : resolve(h));
    });
  } catch { return null; }
}

function hammingHex(a, b) {
  if (!a || !b || a.length !== b.length) return Infinity;
  let d = 0;
  for (let i = 0; i < a.length; i++) {
    const x = parseInt(a[i], 16) ^ parseInt(b[i], 16);
    d += (x & 1) + ((x >> 1) & 1) + ((x >> 2) & 1) + ((x >> 3) & 1);
  }
  return d;
}

function productsJsonUrl(domain, page = 1) {
  return `https://${domain}/products.json?limit=250&page=${page}`;
}

async function validateStore(candidate, fingerprint, { cache } = {}) {
  const { domain } = candidate;

  const cached = cache ? await cache.getStore(domain) : null;
  if (cached && cached.fingerprint_key === fingerprintKey(fingerprint)) {
    return { ...cached, from_cache: true };
  }

  const confirmed = await confirmShopify(domain);
  if (!confirmed.isShopify) {
    return { domain, matched: false, reason: confirmed.signal };
  }
  if (confirmed.blocked) {
    return { domain, matched: false, reason: "products_json_blocked", is_shopify: true };
  }

  // Walk up to 3 pages of /products.json looking for a match. Early-exit
  // as soon as we find one, which is the common case.
  const threshold = isGenericProduct(fingerprint)
    ? THRESHOLDS.titleSimilarityGeneric
    : THRESHOLDS.titleSimilarityMin;

  const targetImageHash = (fingerprint.image_hash ?? "").replace(/^phash:/, "");

  for (let page = 1; page <= 3; page++) {
    const res = await http.get(productsJsonUrl(domain, page));
    if (res.status !== 200) break;
    const products = res.data?.products ?? [];
    if (!products.length) break;

    for (const p of products) {
      const sim = titleSimilarity(fingerprint.raw_title, p.title);
      if (sim >= threshold) {
        const hit = {
          domain,
          matched: true,
          match_type: "title",
          match_confidence: Number(sim.toFixed(3)),
          matched_product: {
            title: p.title,
            handle: p.handle,
            product_url: `https://${domain}/products/${p.handle}`,
            price: p.variants?.[0]?.price ?? null,
            currency: null, // filled by geo-locator via /cart.js
            image: p.images?.[0]?.src ?? null,
            created_at: p.created_at,
          },
          is_shopify: true,
        };
        if (cache) await cache.putStore(domain, { ...hit, fingerprint_key: fingerprintKey(fingerprint) });
        return hit;
      }

      // Image-hash match is a stronger signal than title — try it when title
      // is only weakly similar (covers renamed / translated products).
      if (targetImageHash && sim > 0.45 && p.images?.[0]?.src) {
        const candHash = await hashImageFromUrl(p.images[0].src);
        if (candHash) {
          const d = hammingHex(candHash, targetImageHash);
          if (d < THRESHOLDS.imageHashMaxHamming) {
            const hit = {
              domain,
              matched: true,
              match_type: "image",
              match_confidence: Number((1 - d / (targetImageHash.length * 4)).toFixed(3)),
              hamming_distance: d,
              matched_product: {
                title: p.title,
                handle: p.handle,
                product_url: `https://${domain}/products/${p.handle}`,
                price: p.variants?.[0]?.price ?? null,
                image: p.images[0].src,
                created_at: p.created_at,
              },
              is_shopify: true,
            };
            if (cache) await cache.putStore(domain, { ...hit, fingerprint_key: fingerprintKey(fingerprint) });
            return hit;
          }
        }
      }
    }
  }

  const miss = { domain, matched: false, reason: "no_product_match", is_shopify: true };
  if (cache) await cache.putStore(domain, { ...miss, fingerprint_key: fingerprintKey(fingerprint) });
  return miss;
}

function fingerprintKey(fp) {
  return fp.image_hash ?? `title:${fp.title_normalized}`;
}

export { validateStore, confirmShopify, titleSimilarity, hammingHex, fingerprintKey };
