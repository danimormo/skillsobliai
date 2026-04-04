from pydantic import BaseModel, Field


class ContentResearchInput(BaseModel):
    keywords: list[str]
    platforms: list[str] = Field(default=["tiktok", "pinterest"])
    region: str = "US"
    limit_per_platform: int = 30


class ContentItem(BaseModel):
    platform: str
    content_id: str
    url: str
    thumbnail_url: str | None = None
    caption: str | None = None
    likes: int
    views: int | None = None
    saves: int | None = None
    engagement_rate: float
    format_type: str  # "ugc" | "demo" | "review" | "lifestyle" | "transformation"
    creative_angle: str  # "problem_solution" | "social_proof" | "lifestyle" | "trend"
    hook_text: str | None = None


class ContentResearchOutput(BaseModel):
    total_items: int
    items: list[ContentItem]
    top_formats: list[str]
    top_angles: list[str]
    avg_engagement_rate: float
    content_insights: str
