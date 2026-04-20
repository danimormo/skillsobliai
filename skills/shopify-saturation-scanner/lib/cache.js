// Supabase-backed cache for the network-effect model (cross-tenant):
//   - product_fingerprints: dedup scans by image hash / normalized title
//   - shopify_stores_cache: store-level findings shared across users (24h TTL)
//
// The helpers gracefully no-op when SUPABASE_* env vars are missing, so
// local dev and tests still run.

import { createClient } from "@supabase/supabase-js";
import { API_KEYS } from "../config/api-keys.js";
import { THRESHOLDS } from "../config/thresholds.js";
import { fingerprintCacheKey } from "./fingerprint.js";

let _client = null;
function client() {
  if (_client) return _client;
  if (!API_KEYS.supabase.url || !API_KEYS.supabase.serviceKey) return null;
  _client = createClient(API_KEYS.supabase.url, API_KEYS.supabase.serviceKey, {
    auth: { persistSession: false },
  });
  return _client;
}

async function getFingerprintScan(fp) {
  const sb = client();
  if (!sb) return null;
  const key = fingerprintCacheKey(fp);
  const { data } = await sb
    .from("saturation_scans_cache")
    .select("*")
    .eq("fingerprint_key", key)
    .gt("expires_at", new Date().toISOString())
    .maybeSingle();
  return data?.result ?? null;
}

async function putFingerprintScan(fp, result) {
  const sb = client();
  if (!sb) return;
  const key = fingerprintCacheKey(fp);
  const expires = new Date(Date.now() + THRESHOLDS.fingerprintTtlSec * 1000).toISOString();
  await sb
    .from("saturation_scans_cache")
    .upsert({ fingerprint_key: key, result, expires_at: expires, updated_at: new Date().toISOString() });
}

async function getStore(domain) {
  const sb = client();
  if (!sb) return null;
  const { data } = await sb
    .from("shopify_stores_cache")
    .select("*")
    .eq("domain", domain)
    .gt("expires_at", new Date().toISOString())
    .maybeSingle();
  return data ?? null;
}

async function putStore(domain, payload) {
  const sb = client();
  if (!sb) return;
  const expires = new Date(Date.now() + THRESHOLDS.storeLookupTtlSec * 1000).toISOString();
  await sb
    .from("shopify_stores_cache")
    .upsert({
      domain,
      is_shopify: payload.is_shopify ?? false,
      primary_market: payload.primary_market ?? null,
      fingerprint_key: payload.fingerprint_key ?? null,
      match_payload: payload,
      expires_at: expires,
      updated_at: new Date().toISOString(),
    });
}

export const storeCache = { getStore, putStore };
export const scanCache = { getFingerprintScan, putFingerprintScan };
