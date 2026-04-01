from pydantic import BaseModel, Field


class GoogleResearchInput(BaseModel):
    keywords: list[str]
    region: str = "US"
    reddit_subreddits: list[str] = Field(default=[])
    trends_days: int = 90


class TrendDataPoint(BaseModel):
    date: str
    value: int  # 0-100 relative


class RedditPost(BaseModel):
    title: str
    subreddit: str
    score: int
    url: str
    sentiment: str  # "positive" | "negative" | "neutral"
    key_phrases: list[str] = []


class GoogleResearchOutput(BaseModel):
    keyword: str
    trend_direction: str  # "rising" | "stable" | "declining"
    trend_data: list[TrendDataPoint]
    peak_months: list[str]
    reddit_posts: list[RedditPost]
    overall_sentiment: str
    estimated_monthly_searches: int | None = None
    estimated_cpc_usd: float | None = None
    demand_score: int  # 0-100
