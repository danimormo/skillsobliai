from pydantic import BaseModel, Field


class TikTokAdsResearchInput(BaseModel):
    keywords: list[str]
    regions: list[str] = Field(default=["US", "GB"])
    industry: str | None = None
    days_range: int = 30
    limit: int = 50


class TikTokAd(BaseModel):
    ad_id: str
    advertiser_name: str
    video_url: str | None = None
    thumbnail_url: str | None = None
    caption: str | None = None
    cta_text: str | None = None
    likes: int
    comments: int
    shares: int
    views: int = 0
    engagement_rate: float
    estimated_spend: str | None = None
    region: str
    industry: str | None = None
    duration_seconds: float | None = None
    is_active: bool


class TikTokAdsResearchOutput(BaseModel):
    total_ads: int
    ads: list[TikTokAd]
    keywords: list[str]
    regions: list[str]
