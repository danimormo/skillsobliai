from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── INFRASTRUTTURA ───────────────────────────────────────────
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    REDIS_URL: str = "redis://localhost:6379"
    SENTRY_DSN: str = ""
    ENV: str = "development"
    DEBUG: bool = False

    # ── ANTHROPIC ────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL_FAST: str = "claude-haiku-4-5-20251001"
    ANTHROPIC_MODEL_QUALITY: str = "claude-sonnet-4-6"

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

    # ── GOOGLE CLOUD (Vertex AI + Vision API) ────────────────────
    GOOGLE_APPLICATION_CREDENTIALS: str = ""
    GOOGLE_CLOUD_PROJECT: str = ""
    GOOGLE_CLOUD_LOCATION: str = "us-central1"
    VERTEX_IMAGE_MODEL: str = "imagegeneration@006"
    VERTEX_VIDEO_MODEL: str = "veo-002"

    # ── TREND ANALYZER (SKILL 24) ────────────────────────────────
    TREND_ANALYZER_COST_CAP_USD: float = 0.05
    TREND_ANALYZER_PLAYWRIGHT_HEADLESS: bool = True

    class Config:
        env_file = ".env"


settings = Settings()
