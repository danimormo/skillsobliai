"""Content Researcher skill -- discovers trending organic content across platforms."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import Counter
from typing import Any

from core.errors import InvalidParamsError
from core.skill_interface import BaseSkill, SkillContext, SkillResult
from core.supabase_client import get_supabase

from SKILLS.content_researcher import api_client, cache
from SKILLS.content_researcher.schemas import (
    ContentItem,
    ContentResearchInput,
    ContentResearchOutput,
)

logger = logging.getLogger(__name__)

SKILL_NAME = "content-researcher"

_SUPPORTED_PLATFORMS = {"tiktok", "pinterest"}


# ── Classification helpers ──────────────────────────────────────────────


def _classify_format_type(text: str, platform: str) -> str:
    """Classify the content format type from caption / description text."""
    lower = text.lower() if text else ""
    if "review" in lower:
        return "review"
    if ("transform" in lower) or ("before" in lower and "after" in lower):
        return "transformation"
    if "demo" in lower or "how to" in lower or "tutorial" in lower:
        return "demo"
    if "try" in lower or "unbox" in lower or "honest" in lower:
        return "ugc"
    if "lifestyle" in lower or "routine" in lower or "day in" in lower or "aesthetic" in lower:
        return "lifestyle"
    # Default heuristic per platform
    return "ugc" if platform == "tiktok" else "lifestyle"


def _classify_creative_angle(text: str) -> str:
    """Classify the creative angle from caption / description text."""
    lower = text.lower() if text else ""
    if any(w in lower for w in ("problem", "solution", "before", "after", "struggle", "fix")):
        return "problem_solution"
    if any(w in lower for w in ("everyone", "viral", "million", "sold out", "best seller")):
        return "social_proof"
    if any(w in lower for w in ("trend", "trending", "new", "just dropped", "hack")):
        return "trend"
    return "lifestyle"


def _extract_hook(caption: str | None) -> str | None:
    """Extract hook text from the first line of a caption."""
    if not caption:
        return None
    first_line = caption.split("\n")[0].strip()
    return first_line if first_line else None


# ── Platform-specific item builders ─────────────────────────────────────


def _build_tiktok_item(raw: dict[str, Any]) -> ContentItem | None:
    """Build a ContentItem from a raw TikTok video dict."""
    content_id = str(raw.get("id", raw.get("video_id", "")))
    if not content_id:
        return None

    likes = int(raw.get("likes", raw.get("digg_count", 0)))
    views = int(raw.get("views", raw.get("play_count", 0)))
    caption = raw.get("caption", raw.get("desc", ""))

    engagement_rate = (likes / views) if views > 0 else 0.0

    return ContentItem(
        platform="tiktok",
        content_id=content_id,
        url=raw.get("url", raw.get("video_url", f"https://www.tiktok.com/@/video/{content_id}")),
        thumbnail_url=raw.get("thumbnail_url", raw.get("cover", None)),
        caption=caption,
        likes=likes,
        views=views,
        saves=int(raw.get("saves", raw.get("collect_count", 0))) or None,
        engagement_rate=round(engagement_rate, 6),
        format_type=_classify_format_type(caption, "tiktok"),
        creative_angle=_classify_creative_angle(caption),
        hook_text=_extract_hook(caption),
    )


def _build_pinterest_item(raw: dict[str, Any]) -> ContentItem | None:
    """Build a ContentItem from a raw Pinterest pin dict."""
    content_id = str(raw.get("id", raw.get("pin_id", "")))
    if not content_id:
        return None

    likes = int(raw.get("likes", raw.get("reaction_counts", {}).get("like", 0)))
    saves = int(raw.get("saves", raw.get("save_count", raw.get("repin_count", 0))))
    description = raw.get("description", raw.get("caption", ""))

    engagement_rate = saves / (saves + likes + 1)

    return ContentItem(
        platform="pinterest",
        content_id=content_id,
        url=raw.get("url", raw.get("link", f"https://www.pinterest.com/pin/{content_id}/")),
        thumbnail_url=raw.get("thumbnail_url", raw.get("image_url", None)),
        caption=description,
        likes=likes,
        views=None,
        saves=saves,
        engagement_rate=round(engagement_rate, 6),
        format_type=_classify_format_type(description, "pinterest"),
        creative_angle=_classify_creative_angle(description),
        hook_text=_extract_hook(description),
    )


# ── Insights generator ──────────────────────────────────────────────────


def _generate_insights(items: list[ContentItem], top_formats: list[str], top_angles: list[str]) -> str:
    """Generate a human-readable insights summary."""
    if not items:
        return "No content items were found for the given keywords and platforms."

    platform_counts: dict[str, int] = Counter(i.platform for i in items)
    platform_summary = ", ".join(f"{count} from {plat}" for plat, count in platform_counts.items())

    avg_eng = sum(i.engagement_rate for i in items) / len(items)

    parts = [
        f"Analyzed {len(items)} content items ({platform_summary}).",
        f"Average engagement rate: {avg_eng:.2%}.",
    ]

    if top_formats:
        parts.append(f"Top-performing formats: {', '.join(top_formats)}.")
    if top_angles:
        parts.append(f"Most common creative angles: {', '.join(top_angles)}.")

    # Highlight high-engagement items
    high_eng = [i for i in items if i.engagement_rate > avg_eng * 1.5]
    if high_eng:
        parts.append(
            f"{len(high_eng)} items have engagement rates >1.5x the average -- "
            f"study these for winning hooks and formats."
        )

    return " ".join(parts)


# ── Skill class ──────────────────────────────────────────────────────────


class ContentResearcherSkill(BaseSkill[ContentResearchInput, ContentResearchOutput]):
    name = SKILL_NAME
    version = "1.0.0"
    description = "Discover trending organic content across TikTok and Pinterest"
    consumes_credits = True
    credit_cost = 1

    def validate(self, input: ContentResearchInput) -> bool:
        if not input.keywords:
            raise InvalidParamsError(
                message="keywords must not be empty",
                skill=SKILL_NAME,
                code="INVALID_PARAMS",
            )
        unsupported = set(input.platforms) - _SUPPORTED_PLATFORMS
        if unsupported:
            raise InvalidParamsError(
                message=f"Unsupported platforms: {unsupported}. Supported: {_SUPPORTED_PLATFORMS}",
                skill=SKILL_NAME,
                code="INVALID_PARAMS",
            )
        return True

    async def run(
        self, input: ContentResearchInput, ctx: SkillContext
    ) -> SkillResult[ContentResearchOutput]:
        start = time.perf_counter()
        self.validate(input)

        # ── Check cache ─────────────────────────────────────────────
        cache_params = input.model_dump()
        cached_data = await cache.get_cached(ctx.user_id, cache_params)
        if cached_data is not None:
            output = ContentResearchOutput(**cached_data)
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return SkillResult(
                success=True,
                data=output,
                cached=True,
                execution_ms=elapsed_ms,
            )

        # ── Fetch content from upstream ─────────────────────────────
        tasks: list[asyncio.Task[Any]] = []
        task_meta: list[tuple[str, str]] = []  # (platform, keyword)

        for keyword in input.keywords:
            for platform in input.platforms:
                if platform == "tiktok":
                    tasks.append(
                        api_client.search_tiktok(
                            keyword=keyword,
                            region=input.region,
                            limit=input.limit_per_platform,
                        )
                    )
                elif platform == "pinterest":
                    tasks.append(
                        api_client.search_pinterest(
                            keyword=keyword,
                            region=input.region,
                            limit=input.limit_per_platform,
                        )
                    )
                task_meta.append((platform, keyword))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # ── Build and deduplicate items ─────────────────────────────
        seen: dict[str, ContentItem] = {}
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning("Skipping failed fetch: %s", result)
                continue
            platform = task_meta[idx][0]
            if not isinstance(result, list):
                continue
            for raw in result:
                if platform == "tiktok":
                    item = _build_tiktok_item(raw)
                else:
                    item = _build_pinterest_item(raw)
                if item is None:
                    continue
                dedup_key = f"{item.platform}:{item.content_id}"
                if dedup_key not in seen:
                    seen[dedup_key] = item

        items = list(seen.values())

        # ── Compute aggregations ────────────────────────────────────
        format_counts = Counter(i.format_type for i in items)
        angle_counts = Counter(i.creative_angle for i in items)

        top_formats = [fmt for fmt, _ in format_counts.most_common(3)]
        top_angles = [angle for angle, _ in angle_counts.most_common(3)]
        avg_engagement_rate = round(
            sum(i.engagement_rate for i in items) / len(items), 6
        ) if items else 0.0

        content_insights = _generate_insights(items, top_formats, top_angles)

        output = ContentResearchOutput(
            total_items=len(items),
            items=items,
            top_formats=top_formats,
            top_angles=top_angles,
            avg_engagement_rate=avg_engagement_rate,
            content_insights=content_insights,
        )

        # ── Persist to Supabase ─────────────────────────────────────
        try:
            supabase = get_supabase()
            supabase.table("research_results").insert(
                {
                    "user_id": ctx.user_id,
                    "skill": SKILL_NAME,
                    "query_params": input.model_dump(),
                    "result": output.model_dump(),
                    "items_count": output.total_items,
                }
            ).execute()
        except Exception:
            logger.exception("Failed to persist research results to Supabase")

        # ── Cache result ────────────────────────────────────────────
        await cache.set_cached(ctx.user_id, cache_params, output.model_dump())

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return SkillResult(
            success=True,
            data=output,
            cached=False,
            execution_ms=elapsed_ms,
        )
