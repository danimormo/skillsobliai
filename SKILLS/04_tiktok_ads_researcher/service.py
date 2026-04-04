import asyncio
import logging
import time
from datetime import datetime, timezone

from core.skill_interface import BaseSkill, SkillContext, SkillResult
from core.supabase_client import get_supabase

from . import api_client, cache
from .schemas import (
    TikTokAd,
    TikTokAdsResearchInput,
    TikTokAdsResearchOutput,
)

logger = logging.getLogger(__name__)

SKILL_NAME = "tiktok-ads-researcher"


class TikTokAdsResearcherSkill(BaseSkill[TikTokAdsResearchInput, TikTokAdsResearchOutput]):
    name = SKILL_NAME
    version = "1.0.0"
    description = "Research TikTok ads by keywords and regions via ScrapeCreators"
    consumes_credits = True
    credit_cost = 1

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self, input: TikTokAdsResearchInput) -> bool:
        if not input.keywords:
            return False
        if input.limit < 1 or input.limit > 200:
            return False
        if input.days_range < 1 or input.days_range > 365:
            return False
        return True

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    async def run(
        self,
        input: TikTokAdsResearchInput,
        ctx: SkillContext,
    ) -> SkillResult[TikTokAdsResearchOutput]:
        start = time.perf_counter()

        # Build a cache-key-friendly param dict
        cache_params = input.model_dump()

        # 1. Check cache
        cached_data = await cache.get_cached(ctx.user_id, cache_params)
        if cached_data is not None:
            output = TikTokAdsResearchOutput(**cached_data)
            elapsed = int((time.perf_counter() - start) * 1000)
            return SkillResult(
                success=True,
                data=output,
                cached=True,
                execution_ms=elapsed,
            )

        # 2. Fetch from upstream: keyword x region matrix (concurrent)
        fetch_tasks = []
        fetch_meta: list[tuple[str, str]] = []  # (keyword, region)
        for keyword in input.keywords:
            for region in input.regions:
                fetch_tasks.append(
                    api_client.fetch_ads(
                        keyword=keyword,
                        region=region,
                        industry=input.industry,
                        days=input.days_range,
                        limit=input.limit,
                    )
                )
                fetch_meta.append((keyword, region))

        results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

        seen_ids: set[str] = set()
        ads: list[TikTokAd] = []

        for idx, raw in enumerate(results):
            if isinstance(raw, Exception):
                logger.warning("Skipping failed fetch for %s: %s", fetch_meta[idx], raw)
                continue

            _, region = fetch_meta[idx]
            for item in raw.get("ads", raw.get("data", [])):
                ad_id = str(item.get("ad_id", item.get("id", "")))
                if not ad_id or ad_id in seen_ids:
                    continue
                seen_ids.add(ad_id)

                ads.append(
                    TikTokAd(
                        ad_id=ad_id,
                        advertiser_name=item.get("advertiser_name", ""),
                        video_url=item.get("video_url"),
                        thumbnail_url=item.get("thumbnail_url"),
                        caption=item.get("caption"),
                        cta_text=item.get("cta_text"),
                        likes=int(item.get("likes", 0)),
                        comments=int(item.get("comments", 0)),
                        shares=int(item.get("shares", 0)),
                        views=int(item.get("views", 0)),
                        engagement_rate=float(item.get("engagement_rate", 0.0)),
                        estimated_spend=item.get("estimated_spend"),
                        region=item.get("region", region),
                        industry=item.get("industry", input.industry),
                        duration_seconds=item.get("duration_seconds"),
                        is_active=bool(item.get("is_active", True)),
                    )
                )

        output = TikTokAdsResearchOutput(
            total_ads=len(ads),
            ads=ads,
            keywords=input.keywords,
            regions=input.regions,
        )

        # 3. Persist to Supabase
        try:
            supabase = get_supabase()
            supabase.table("research_results").insert(
                {
                    "user_id": ctx.user_id,
                    "skill": SKILL_NAME,
                    "query_params": input.model_dump(),
                    "result": output.model_dump(),
                    "items_count": len(ads),
                }
            ).execute()
        except Exception:
            logger.exception("Failed to persist research results to Supabase")

        # 4. Cache the result
        await cache.set_cached(ctx.user_id, cache_params, output.model_dump())

        elapsed = int((time.perf_counter() - start) * 1000)
        return SkillResult(
            success=True,
            data=output,
            cached=False,
            execution_ms=elapsed,
        )
