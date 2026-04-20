from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


# ── Input ──────────────────────────────────────────────────────────────────

InputKind = Literal["text", "url", "image"]


class TrendAnalyzerInput(BaseModel):
    """Single entrypoint that accepts any of: free text, product URL, image.

    Exactly one of text / url / image_url / image_b64 must be provided.
    """

    text: str | None = None
    url: HttpUrl | None = None
    image_url: HttpUrl | None = None
    image_b64: str | None = Field(
        default=None,
        description="Base64-encoded image bytes (JPG/PNG/WEBP). Mutually exclusive with image_url.",
    )

    countries: list[str] = Field(
        default_factory=lambda: ["US", "GB", "IT", "FR", "DE", "ES"],
        description="ISO-3166-1 alpha-2 codes for geo analysis.",
    )
    skip_creatives: bool = False
    fast: bool = Field(default=False, description="Skip tier-3 providers (Reddit, YouTube).")
    no_cache: bool = False
    force: bool = Field(
        default=False,
        description="Bypass cost hard-cap (use with care in production).",
    )


# ── Product fingerprint ────────────────────────────────────────────────────


Category = Literal[
    "fashion",
    "home",
    "beauty",
    "electronics",
    "fitness",
    "pets",
    "kids",
    "kitchen",
    "outdoor",
    "other",
]


class ProductFingerprint(BaseModel):
    primary_keyword: str = Field(..., description="Short searchable phrase (2-4 words, EN).")
    secondary_keywords: list[str] = Field(default_factory=list, max_length=5)
    category: Category = "other"
    estimated_retail_price_usd: float | None = None
    product_attributes: list[str] = Field(default_factory=list, max_length=5)
    source_kind: InputKind
    raw_input: str = Field(default="", description="Echo of the raw input for traceability.")


# ── Sub-scores ─────────────────────────────────────────────────────────────


class SubScore(BaseModel):
    name: Literal["momentum", "saturation", "ad_velocity", "seasonality", "margin"]
    value: float = Field(..., ge=0, le=100)
    weight: float = Field(..., ge=0, le=1)
    explanation: str


# ── Provider outputs ───────────────────────────────────────────────────────


class InterestPoint(BaseModel):
    date: date
    value: int = Field(..., ge=0, le=100)


class GeoInterest(BaseModel):
    country: str
    current_value: int
    delta_pct: float = Field(..., description="(last_30d - prior_90d) / prior_90d * 100")


class MetaAdsSignal(BaseModel):
    active_ads_7d: int = 0
    active_ads_30d: int = 0
    top_advertisers: list[str] = Field(default_factory=list)
    earliest_ad_date: date | None = None
    media_distribution: dict[str, int] = Field(
        default_factory=dict,
        description="e.g. {'image': 12, 'video': 34, 'carousel': 5}",
    )


class TikTokSignal(BaseModel):
    hashtag_score: float | None = None
    top_videos_views: list[int] = Field(default_factory=list)
    product_mentions: int = 0


class CompetitorStore(BaseModel):
    domain: str
    product_url: HttpUrl | None = None
    price_usd: float | None = None
    first_ad_seen: date | None = None


class SaturationSignal(BaseModel):
    stores_found: int = 0
    top_competitors: list[CompetitorStore] = Field(default_factory=list, max_length=5)


class PriceSignal(BaseModel):
    retail_price_median_usd: float | None = None
    retail_price_range_usd: tuple[float, float] | None = None
    supplier_price_median_usd: float | None = None
    gross_margin_pct: float | None = None


class TrendsSignal(BaseModel):
    """Aggregated output of the Google Trends provider."""

    interest_over_time: list[InterestPoint] = Field(default_factory=list)
    geography: list[GeoInterest] = Field(default_factory=list, max_length=5)
    related_queries_rising: list[str] = Field(default_factory=list, max_length=10)
    related_queries_top: list[str] = Field(default_factory=list, max_length=10)
    stale: bool = Field(
        default=False,
        description="True when the value was served from expired cache due to upstream failure.",
    )


class SeasonalityInfo(BaseModel):
    peak_months: list[str] = Field(default_factory=list, description="e.g. ['Nov', 'Dec']")
    valley_months: list[str] = Field(default_factory=list)
    summary: str = ""


# ── Creatives ──────────────────────────────────────────────────────────────


class CreativeAngle(BaseModel):
    name: str
    description: str
    target_emotion: str
    format_hint: str = Field(default="UGC", description="UGC / static / carousel / talking-head")


class HookCopy(BaseModel):
    text: str
    style: str = Field(default="problem-agitate", description="hook archetype")


class CreativesBlock(BaseModel):
    angles: list[CreativeAngle] = Field(default_factory=list, max_length=5)
    hooks: list[HookCopy] = Field(default_factory=list, max_length=5)


# ── Cost tracking ──────────────────────────────────────────────────────────


class CostEntry(BaseModel):
    provider: str
    operation: str
    usd: float
    units: int = 1
    note: str = ""


class CostBreakdown(BaseModel):
    total_usd: float = 0.0
    entries: list[CostEntry] = Field(default_factory=list)
    cap_hit: bool = False
    cap_usd: float = 0.05


# ── Final report ───────────────────────────────────────────────────────────


Verdict = Literal["GO", "WAIT", "AVOID"]


class TrendReport(BaseModel):
    fingerprint: ProductFingerprint

    score: float = Field(..., ge=0, le=100)
    verdict: Verdict
    rationale: str

    sub_scores: list[SubScore]

    interest_over_time: list[InterestPoint] = Field(default_factory=list)
    seasonality: SeasonalityInfo = Field(default_factory=SeasonalityInfo)

    saturation: SaturationSignal = Field(default_factory=SaturationSignal)
    meta_ads: MetaAdsSignal = Field(default_factory=MetaAdsSignal)
    tiktok: TikTokSignal = Field(default_factory=TikTokSignal)

    geography: list[GeoInterest] = Field(default_factory=list, max_length=5)
    price: PriceSignal = Field(default_factory=PriceSignal)

    creatives: CreativesBlock = Field(default_factory=CreativesBlock)

    cost: CostBreakdown = Field(default_factory=CostBreakdown)
    warnings: list[str] = Field(default_factory=list)


class TrendAnalyzerOutput(BaseModel):
    report: TrendReport
    markdown: str = Field(default="", description="Human-readable rendering of the report.")
