"""Pydantic schemas for TikTok Shop Researcher."""

from __future__ import annotations

from pydantic import BaseModel


class TikTokShopInput(BaseModel):
    countries: list[str]
    keywords_by_country: dict[str, list[str]] = {}
    n_results: int = 10
    fetch_limit: int | None = None


class TikTokShopProduct(BaseModel):
    item_id: str
    source: str = "tiktok_shop"
    title: str
    image_url: str
    product_url: str
    price: float
    currency: str
    country: str
    sold_count: int
    rating: float
    trust_label: str | None = None
    creator_video: dict | None = None
    velocity_signal: str
    new_arrival: bool
    seo_url_updated_at: str | None = None


class TikTokShopOutput(BaseModel):
    total_fetched: int
    total_after_filter: int
    products: list[TikTokShopProduct]
    countries_searched: list[str]
    countries_skipped: list[str]
    filter_tier_used: int
