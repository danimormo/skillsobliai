"""GoogleResearcherSkill -- trend analysis and Reddit sentiment for keywords."""

from __future__ import annotations

import logging
import re
import time
from collections import Counter
from typing import Any

from core.errors import InvalidParamsError
from core.skill_interface import BaseSkill, SkillContext, SkillResult
from core.supabase_client import get_supabase

from SKILLS.05_google_researcher import api_client, cache
from SKILLS.05_google_researcher.schemas import (
    GoogleResearchInput,
    GoogleResearchOutput,
    RedditPost,
    TrendDataPoint,
)

logger = logging.getLogger(__name__)

SKILL_NAME = "google-researcher"

# ── Helpers ──────────────────────────────────────────────────────────────


def _compute_trend_direction(data_points: list[dict[str, Any]]) -> str:
    """Compare first 30-day avg vs last 30-day avg to determine direction."""
    if not data_points:
        return "stable"
    values = [p.get("value", 0) for p in data_points]
    n = min(30, len(values) // 2) or 1
    first_avg = sum(values[:n]) / n
    last_avg = sum(values[-n:]) / n
    if last_avg > first_avg * 1.15:
        return "rising"
    if last_avg < first_avg * 0.85:
        return "declining"
    return "stable"


def _find_peak_months(data_points: list[dict[str, Any]]) -> list[str]:
    """Return months (YYYY-MM) that contain a data point with value >= 80."""
    months: set[str] = set()
    for point in data_points:
        if point.get("value", 0) >= 80:
            date_str = point.get("date", "")
            if len(date_str) >= 7:
                months.add(date_str[:7])
    return sorted(months)


def _extract_key_phrases(title: str) -> list[str]:
    """Extract simple key phrases (2-3 word chunks) from a post title."""
    words = re.findall(r"[a-zA-Z]{3,}", title.lower())
    if len(words) < 2:
        return words
    phrases: list[str] = []
    for i in range(len(words) - 1):
        phrases.append(f"{words[i]} {words[i + 1]}")
    return phrases[:5]


def _sentiment_from_score(score: int) -> str:
    if score > 10:
        return "positive"
    if score < 0:
        return "negative"
    return "neutral"


def _overall_sentiment(posts: list[RedditPost]) -> str:
    if not posts:
        return "neutral"
    counts = Counter(p.sentiment for p in posts)
    return counts.most_common(1)[0][0]


def _calculate_demand_score(
    trend_values: list[int],
    reddit_posts: list[RedditPost],
) -> int:
    """0-100 score based on average trend value (60%) and reddit engagement (40%)."""
    # Trend component: average of values (already 0-100 scale)
    trend_avg = sum(trend_values) / len(trend_values) if trend_values else 0
    trend_component = trend_avg * 0.6

    # Reddit component: scale total upvotes (cap at 100)
    total_score = sum(max(p.score, 0) for p in reddit_posts)
    reddit_norm = min(total_score / 500, 1.0) * 100  # 500 total upvotes => max
    reddit_component = reddit_norm * 0.4

    return max(0, min(100, int(trend_component + reddit_component)))


# ── Skill ────────────────────────────────────────────────────────────────


class GoogleResearcherSkill(BaseSkill[GoogleResearchInput, GoogleResearchOutput]):
    name = SKILL_NAME
    version = "1.0.0"
    description = "Analyse Google Trends and Reddit sentiment for product/niche keywords"
    consumes_credits = True
    credit_cost = 1

    def validate(self, input: GoogleResearchInput) -> bool:
        if not input.keywords:
            raise InvalidParamsError(
                message="keywords must not be empty",
                skill=SKILL_NAME,
                code="INVALID_PARAMS",
            )
        return True

    async def run(
        self, input: GoogleResearchInput, ctx: SkillContext
    ) -> SkillResult[GoogleResearchOutput]:
        start = time.perf_counter()
        self.validate(input)

        # ── Check cache ─────────────────────────────────────────────
        cache_params = input.model_dump()
        cached_data = await cache.get_cached(ctx.user_id, cache_params)
        if cached_data is not None:
            output = GoogleResearchOutput(**cached_data)
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return SkillResult(
                success=True,
                data=output,
                cached=True,
                execution_ms=elapsed_ms,
            )

        # ── Process primary keyword (first) ─────────────────────────
        primary_keyword = input.keywords[0]

        # Fetch Google Trends
        trends_raw = await api_client.fetch_google_trends(
            keyword=primary_keyword,
            region=input.region,
            days=input.trends_days,
        )
        data_points = trends_raw.get("interest_over_time", trends_raw.get("data", []))

        trend_data = [
            TrendDataPoint(date=p.get("date", ""), value=p.get("value", 0))
            for p in data_points
        ]
        trend_direction = _compute_trend_direction(data_points)
        peak_months = _find_peak_months(data_points)
        trend_values = [p.value for p in trend_data]

        # Fetch Reddit posts
        raw_posts = await api_client.search_reddit(
            keyword=primary_keyword,
            subreddits=input.reddit_subreddits or None,
        )

        reddit_posts: list[RedditPost] = []
        for rp in raw_posts:
            score = rp.get("score", rp.get("ups", 0))
            title = rp.get("title", "")
            reddit_posts.append(
                RedditPost(
                    title=title,
                    subreddit=rp.get("subreddit", ""),
                    score=score,
                    url=rp.get("url", rp.get("permalink", "")),
                    sentiment=_sentiment_from_score(score),
                    key_phrases=_extract_key_phrases(title),
                )
            )

        demand_score = _calculate_demand_score(trend_values, reddit_posts)

        # ── Shopify competitor search (optional) ───────────────────
        shopify_competitors: list[str] = []
        if input.find_shopify_competitors:
            try:
                query = f'site:myshopify.com "{primary_keyword}"'
                results = await api_client.search_google(
                    client=None,
                    query=query,
                    limit=10,
                )
                for r in results:
                    url = r.get("url", r.get("link", ""))
                    if url and "myshopify.com" in url:
                        shopify_competitors.append(url)
            except Exception:
                logger.exception("Failed to fetch Shopify competitors for %s", primary_keyword)

        output = GoogleResearchOutput(
            keyword=primary_keyword,
            trend_direction=trend_direction,
            trend_data=trend_data,
            peak_months=peak_months,
            reddit_posts=reddit_posts,
            overall_sentiment=_overall_sentiment(reddit_posts),
            estimated_monthly_searches=trends_raw.get("estimated_monthly_searches"),
            estimated_cpc_usd=trends_raw.get("estimated_cpc_usd"),
            demand_score=demand_score,
            shopify_competitors=shopify_competitors,
        )

        # ── Process remaining keywords (save only, not returned) ────
        for kw in input.keywords[1:]:
            try:
                kw_trends = await api_client.fetch_google_trends(
                    keyword=kw, region=input.region, days=input.trends_days,
                )
                kw_posts = await api_client.search_reddit(
                    keyword=kw, subreddits=input.reddit_subreddits or None,
                )
                kw_data_points = kw_trends.get(
                    "interest_over_time", kw_trends.get("data", [])
                )
                kw_trend_data = [
                    TrendDataPoint(date=p.get("date", ""), value=p.get("value", 0))
                    for p in kw_data_points
                ]
                kw_reddit: list[RedditPost] = []
                for rp in kw_posts:
                    sc = rp.get("score", rp.get("ups", 0))
                    t = rp.get("title", "")
                    kw_reddit.append(
                        RedditPost(
                            title=t,
                            subreddit=rp.get("subreddit", ""),
                            score=sc,
                            url=rp.get("url", rp.get("permalink", "")),
                            sentiment=_sentiment_from_score(sc),
                            key_phrases=_extract_key_phrases(t),
                        )
                    )
                kw_output = GoogleResearchOutput(
                    keyword=kw,
                    trend_direction=_compute_trend_direction(kw_data_points),
                    trend_data=kw_trend_data,
                    peak_months=_find_peak_months(kw_data_points),
                    reddit_posts=kw_reddit,
                    overall_sentiment=_overall_sentiment(kw_reddit),
                    estimated_monthly_searches=kw_trends.get("estimated_monthly_searches"),
                    estimated_cpc_usd=kw_trends.get("estimated_cpc_usd"),
                    demand_score=_calculate_demand_score(
                        [p.value for p in kw_trend_data], kw_reddit
                    ),
                )
                # Persist secondary keyword result
                try:
                    supabase = get_supabase()
                    supabase.table("research_results").insert(
                        {
                            "user_id": ctx.user_id,
                            "skill": SKILL_NAME,
                            "query_params": {"keyword": kw, "region": input.region},
                            "result": kw_output.model_dump(),
                            "items_count": 1,
                        }
                    ).execute()
                except Exception:
                    logger.exception("Failed to persist secondary keyword %s", kw)
            except Exception:
                logger.exception("Failed to process secondary keyword %s", kw)

        # ── Persist primary result to Supabase ──────────────────────
        try:
            supabase = get_supabase()
            supabase.table("research_results").insert(
                {
                    "user_id": ctx.user_id,
                    "skill": SKILL_NAME,
                    "query_params": input.model_dump(),
                    "result": output.model_dump(),
                    "items_count": len(output.trend_data),
                }
            ).execute()
        except Exception:
            logger.exception("Failed to persist research results to Supabase")

        # ── Cache and return ────────────────────────────────────────
        await cache.set_cached(ctx.user_id, cache_params, output.model_dump())

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return SkillResult(
            success=True,
            data=output,
            cached=False,
            execution_ms=elapsed_ms,
        )
