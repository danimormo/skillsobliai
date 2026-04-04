from pydantic import BaseModel, Field


class SaturationDetectorInput(BaseModel):
    product_title: str
    product_keywords: list[str] = []
    sample_size: int = Field(default=100, le=500)
    product_image_url: str | None = None


class SaturationDetectorOutput(BaseModel):
    product_title: str
    stores_found: int
    stores_sampled: int
    saturation_index: float  # 0.0-1.0
    saturation_level: str  # "low" | "medium" | "high" | "very_high"
    flag: str  # "green" | "yellow" | "red"
    recommendation: str
    found_in_stores: list[str]
