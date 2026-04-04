CREATE TABLE IF NOT EXISTS user_credits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE,
    plan TEXT NOT NULL DEFAULT 'starter',
    image_credits_used INTEGER NOT NULL DEFAULT 0,
    image_credits_limit INTEGER NOT NULL DEFAULT 50,
    video_credits_used INTEGER NOT NULL DEFAULT 0,
    video_credits_limit INTEGER NOT NULL DEFAULT 0,
    reset_at TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '30 days'),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
