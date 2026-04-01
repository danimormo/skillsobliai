from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Supabase
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str

    # Redis
    REDIS_URL: str

    # ScrapeCreators
    SCRAPECREATORS_API_KEY: str
    SCRAPECREATORS_BASE_URL: str = "https://api.scrapecreators.com"

    # Shopify (per skill 8)
    SHOPIFY_API_VERSION: str = "2024-04"

    # Supplier APIs (per skill 7)
    CJ_ACCESS_TOKEN: str = ""
    SPOCKET_API_KEY: str = ""

    # Sentry
    SENTRY_DSN: str = ""

    # App
    ENV: str = "development"
    DEBUG: bool = False

    class Config:
        env_file = ".env"


settings = Settings()
