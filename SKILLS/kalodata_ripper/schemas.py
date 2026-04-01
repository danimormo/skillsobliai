from pydantic import BaseModel, Field


class KalodataRipperInput(BaseModel):
    product_id: str
    max_videos: int = 5
    min_views: int = 10000
    min_engagement_rate: float = 0.02


class RippedVideo(BaseModel):
    ad_id: str
    storage_url: str
    duration_seconds: float
    views: int
    engagement_rate: float
    suggested_hook_end: float
    suggested_cta_start: float
    thumbnail_url: str | None = None


class KalodataRipperOutput(BaseModel):
    product_id: str
    videos_downloaded: int
    videos: list[RippedVideo]
