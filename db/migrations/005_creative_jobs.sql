CREATE TABLE IF NOT EXISTS creative_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    skill TEXT NOT NULL,
    product_id TEXT,
    input_params JSONB NOT NULL,
    output_urls JSONB DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'pending',
    credits_used INTEGER DEFAULT 0,
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
