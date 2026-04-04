"""Pydantic models for the Video Ripper skill."""

from __future__ import annotations

from pydantic import BaseModel


class VideoRipperInput(BaseModel):
    product_id: str
    product_url: str | None = None
    region: str = "US"
    max_videos: int = 5
    min_views: int = 10000
    min_engagement_rate: float = 0.02


class RippedVideo(BaseModel):
    ad_id: str
    storage_path: str
    signed_url: str
    duration_seconds: float
    views: int
    engagement_rate: float
    hook_end_seconds: float
    cta_start_seconds: float
    thumbnail_url: str | None = None
    source: str  # "shop_videos" | "product_details"


class VideoRipperOutput(BaseModel):
    product_id: str
    videos_downloaded: int
    videos: list[RippedVideo]
    used_product_details_enrichment: bool
