CREATE TABLE IF NOT EXISTS roas_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    campaign_id UUID REFERENCES campaigns(id) ON DELETE CASCADE,
    meta_campaign_id TEXT NOT NULL,
    roas FLOAT NOT NULL,
    spend_usd FLOAT NOT NULL,
    revenue_usd FLOAT NOT NULL,
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    conversions INTEGER DEFAULT 0,
    action_taken TEXT,
    snapshot_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_rs_campaign ON roas_snapshots(campaign_id);
CREATE INDEX idx_rs_time ON roas_snapshots(snapshot_at DESC);
