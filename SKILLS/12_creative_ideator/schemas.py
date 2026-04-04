from pydantic import BaseModel


class CreativeIdeatorInput(BaseModel):
    product_title: str
    product_description: str
    category: str | None = None
    target_audience: str | None = None
    price: float | None = None
    competitor_hooks: list[str] = []
    top_content_angles: list[str] = []
    num_angles: int = 3
    platform: str = "meta"
    language: str = "en"


class CreativeAngle(BaseModel):
    name: str
    hook: str
    script_30s: str
    format: str
    visual_refs: list[str]
    target_emotion: str
    estimated_ctr_tier: str


class CreativeIdeatorOutput(BaseModel):
    product_title: str
    angles: list[CreativeAngle]
    recommended_angle: str
    platform: str
