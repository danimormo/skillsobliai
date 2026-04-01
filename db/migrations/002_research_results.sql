CREATE TABLE IF NOT EXISTS research_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    skill TEXT NOT NULL,
    query_params JSONB NOT NULL,
    result JSONB NOT NULL,
    items_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_research_results_user_skill
    ON research_results(user_id, skill);
CREATE INDEX idx_research_results_created_at
    ON research_results(created_at DESC);
