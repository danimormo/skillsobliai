-- 009_saturation_scanner.sql
-- Tables backing the Shopify Saturation Scanner (Feature V2).
-- Network-effect cache: shared cross-tenant; 24h TTL enforced in code + via a
-- small scheduled job (pg_cron or Railway cron) that deletes expired rows.

BEGIN;

CREATE TABLE IF NOT EXISTS saturation_scans_cache (
  fingerprint_key text PRIMARY KEY,
  result          jsonb        NOT NULL,
  expires_at      timestamptz  NOT NULL,
  updated_at      timestamptz  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS saturation_scans_cache_expires_at_idx
  ON saturation_scans_cache (expires_at);

COMMENT ON TABLE  saturation_scans_cache IS
  'Dedup scan results cross-tenant; keyed by image pHash or normalized title.';

CREATE TABLE IF NOT EXISTS shopify_stores_cache (
  domain           text PRIMARY KEY,
  is_shopify       boolean      NOT NULL DEFAULT false,
  primary_market   text,                     -- ISO 3166 alpha-2
  fingerprint_key  text,                     -- last fingerprint we matched against
  match_payload    jsonb        NOT NULL,
  expires_at       timestamptz  NOT NULL,
  updated_at       timestamptz  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS shopify_stores_cache_expires_at_idx
  ON shopify_stores_cache (expires_at);
CREATE INDEX IF NOT EXISTS shopify_stores_cache_market_idx
  ON shopify_stores_cache (primary_market);

COMMENT ON TABLE shopify_stores_cache IS
  'Per-domain Shopify validation + geo cache; shared cross-tenant (network effect).';

CREATE TABLE IF NOT EXISTS saturation_scan_jobs (
  scan_id     text PRIMARY KEY,
  user_id     text         NOT NULL,
  input       jsonb        NOT NULL,
  status      text         NOT NULL DEFAULT 'queued'
              CHECK (status IN ('queued','running','done','failed','timeout')),
  result      jsonb,
  error       text,
  started_at  timestamptz,
  completed_at timestamptz,
  created_at  timestamptz  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS saturation_scan_jobs_user_idx
  ON saturation_scan_jobs (user_id, created_at DESC);

COMMIT;
