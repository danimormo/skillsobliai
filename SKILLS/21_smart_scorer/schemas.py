from pydantic import BaseModel


class SmartScorerInput(BaseModel):
    product_title: str
    total_ads: int = 0
    active_ads: int = 0
    found_on_meta: bool = False
    found_on_tiktok: bool = False
    found_on_pinterest: bool = False
    shopify_store_count: int = 0
    avg_engagement_rate: float | None = None
    estimated_margin_pct: float | None = None
    gmv_growth_pct: float | None = None


class SmartScorerOutput(BaseModel):
    product_title: str
    score: int
    tier: str  # "S" | "A" | "B" | "C" | "D"
    breakdown: dict
    recommendation: str
