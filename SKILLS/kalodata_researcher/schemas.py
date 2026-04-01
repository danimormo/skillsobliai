from pydantic import BaseModel, Field


class KalodataResearchInput(BaseModel):
    keywords: list[str] = Field(..., max_length=3)
    category: str | None = None
    region: str = "US"
    days_range: int = Field(default=30, ge=1, le=365)
    limit: int = Field(default=20, ge=1, le=100)


class KalodataProduct(BaseModel):
    product_id: str
    title: str
    category: str
    price_range: dict  # {min, max, currency}
    gmv_30d: float
    gmv_growth_pct: float
    units_sold_30d: int
    shop_count: int
    top_shop: str | None = None
    opportunity_score: float
    thumbnail_url: str | None = None


class KalodataResearchOutput(BaseModel):
    total_products: int
    products: list[KalodataProduct]
    region: str
    days_range: int
