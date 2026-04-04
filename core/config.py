from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── INFRASTRUTTURA ───────────────────────────────────────────
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    REDIS_URL: str = "redis://localhost:6379"
    SENTRY_DSN: str = ""
    ENV: str = "development"
    DEBUG: bool = False

    # ── ANTHROPIC (parser + vision — skill A, B) ─────────────────
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-haiku-4-5-20251001"

    # ── SCRAPECREATORS ───────────────────────────────────────────
    SCRAPECREATORS_API_KEY: str = ""
    SCRAPECREATORS_BASE_URL: str = "https://api.scrapecreators.com"

    # ── META GRAPH API ───────────────────────────────────────────
    META_APP_ID: str = ""
    META_APP_SECRET: str = ""
    META_API_VERSION: str = "v19.0"
    META_BASE_URL: str = "https://graph.facebook.com"

    # ── MANUS AI ─────────────────────────────────────────────────
    MANUS_BASE_URL: str = "https://manus.meta.com/api/v1"

    # ── SHOPIFY ──────────────────────────────────────────────────
    SHOPIFY_API_VERSION: str = "2024-04"
    SHOPIFY_PARTNER_API_KEY: str = ""
    SHOPIFY_PARTNER_API_SECRET: str = ""

    # ── FAL.AI ───────────────────────────────────────────────────
    FAL_API_KEY: str = ""
    FAL_BASE_URL: str = "https://fal.run"

    # ── OPENROUTER / DEEPSEEK V3 ─────────────────────────────────
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "deepseek/deepseek-chat"

    # ── CJ DROPSHIPPING ──────────────────────────────────────────
    CJ_API_KEY: str = ""
    CJ_BASE_URL: str = "https://developers.cjdropshipping.com/api2.0/v1"

    # ── SPOCKET ──────────────────────────────────────────────────
    SPOCKET_API_KEY: str = ""
    SPOCKET_BASE_URL: str = "https://api.spocket.co/v2"

    # ── STRIPE ───────────────────────────────────────────────────
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_STARTER: str = ""
    STRIPE_PRICE_GROWTH: str = ""
    STRIPE_PRICE_AGENCY: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
