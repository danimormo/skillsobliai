from pydantic import BaseModel


class ProductScorerInput(BaseModel):
    items: list[dict]
    params: dict
    n_results: int = 10


class ScoredProduct(BaseModel):
    item_id: str
    score: int
    title: str
    image_url: str
    product_url: str
    price: float
    currency: str
    country: str
    source: str
    sold_count: int | None = None
    rating: float | None = None
    trust_label: str | None = None
    category: str
    gender: str
    eu_market_fit: bool
    creator_video: dict | None = None
    score_breakdown: dict


class ProductScorerOutput(BaseModel):
    total_input: int
    total_after_filter: int
    total_returned: int
    products: list[ScoredProduct]
    gender_filter_applied: bool
