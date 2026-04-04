CREATE TABLE IF NOT EXISTS pdp_pages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    shopify_product_id TEXT,
    shop_domain TEXT NOT NULL,
    template_type TEXT NOT NULL DEFAULT 'standard',
    sections JSONB DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
