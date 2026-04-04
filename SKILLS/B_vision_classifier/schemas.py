from pydantic import BaseModel


class ImageItem(BaseModel):
    item_id: str
    image_url: str
    title: str | None = None


class ClassifiedItem(BaseModel):
    item_id: str
    image_url: str
    is_fashion: bool
    confidence: float
    category: str
    subcategory: str
    target_gender: str
    gender: str
    price_tier: str
    style_tags: list[str]
    reasoning: str
    eu_market_fit: bool
    classification_error: str | None = None


class VisionClassifierInput(BaseModel):
    items: list[ImageItem]
    batch_size: int = 5


class VisionClassifierOutput(BaseModel):
    total_processed: int
    total_fashion: int
    total_non_fashion: int
    total_errors: int
    items: list[ClassifiedItem]
