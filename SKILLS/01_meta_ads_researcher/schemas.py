from pydantic import BaseModel, Field


class MetaAdsResearchInput(BaseModel):
    search_terms: list[str] = Field(..., max_length=5)
    countries: list[str] = Field(default=["IT", "FR", "DE", "ES", "GB"])
    active_only: bool = True
    limit_per_term: int = Field(default=50, le=100)


class MetaAd(BaseModel):
    ad_id: str
    page_name: str
    page_id: str
    body: str | None = None
    title: str | None = None
    snapshot_url: str
    landing_url: str | None = None
    platforms: list[str] = []
    start_date: str
    end_date: str | None = None
    is_active: bool
    days_running: int
    countries: list[str] = []


class MetaAdsResearchOutput(BaseModel):
    total_ads: int
    ads: list[MetaAd]
    search_terms: list[str]
    countries: list[str]
    next_cursor: str | None = None
