import asyncio
import logging
import time
from datetime import date, datetime

from core.errors import InvalidParamsError
from core.skill_interface import BaseSkill, SkillContext, SkillResult
from core.supabase_client import get_supabase

from SKILLS.meta_ads_researcher import api_client, cache
from SKILLS.meta_ads_researcher.schemas import (
    MetaAd,
    MetaAdsResearchInput,
    MetaAdsResearchOutput,
)

logger = logging.getLogger(__name__)

SKILL_NAME = "meta-ads-researcher"


class MetaAdsResearcherSkill(BaseSkill[MetaAdsResearchInput, MetaAdsResearchOutput]):
    name = SKILL_NAME
    version = "1.0.0"
    description = "Research competitor ads from the Meta/Facebook Ad Library"
    consumes_credits = True
    credit_cost = 1

    def validate(self, input: MetaAdsResearchInput) -> bool:
        if not input.search_terms:
            raise InvalidParamsError(
                message="search_terms must not be empty",
                skill=SKILL_NAME,
                code="INVALID_PARAMS",
            )
        return True

    async def run(
        self, input: MetaAdsResearchInput, ctx: SkillContext
    ) -> SkillResult[MetaAdsResearchOutput]:
        start = time.perf_counter()
        self.validate(input)

        # ── Check cache ──────────────────────────────────────────────
        cache_params = input.model_dump()
        cached_data = await cache.get_cached(ctx.user_id, cache_params)
        if cached_data is not None:
            output = MetaAdsResearchOutput(**cached_data)
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return SkillResult(
                success=True,
                data=output,
                cached=True,
                execution_ms=elapsed_ms,
            )

        # ── Fetch ads from upstream ──────────────────────────────────
        active_status = "active" if input.active_only else "all"
        today = date.today()

        tasks = [
            api_client.fetch_ads(
                query=term,
                country=country,
                active_status=active_status,
                limit=input.limit_per_term,
            )
            for term in input.search_terms
            for country in input.countries
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # ── Aggregate and deduplicate ────────────────────────────────
        seen: dict[str, MetaAd] = {}
        for result in results:
            if isinstance(result, Exception):
                logger.warning("Skipping failed fetch: %s", result)
                continue
            ads_list = result.get("data", result.get("ads", []))
            if isinstance(ads_list, list):
                for raw_ad in ads_list:
                    ad_id = str(raw_ad.get("ad_id", raw_ad.get("id", "")))
                    if not ad_id or ad_id in seen:
                        continue

                    start_date_str = raw_ad.get("start_date", "")
                    end_date_str = raw_ad.get("end_date")

                    # Calculate days_running
                    try:
                        start_dt = datetime.strptime(start_date_str[:10], "%Y-%m-%d").date()
                        days_running = (today - start_dt).days
                    except (ValueError, TypeError):
                        days_running = 0

                    is_active = end_date_str is None or end_date_str == ""

                    seen[ad_id] = MetaAd(
                        ad_id=ad_id,
                        page_name=raw_ad.get("page_name", ""),
                        page_id=str(raw_ad.get("page_id", "")),
                        body=raw_ad.get("body"),
                        title=raw_ad.get("title"),
                        snapshot_url=raw_ad.get("snapshot_url", ""),
                        landing_url=raw_ad.get("landing_url"),
                        platforms=raw_ad.get("platforms", []),
                        start_date=start_date_str,
                        end_date=end_date_str if end_date_str else None,
                        is_active=is_active,
                        days_running=days_running,
                        countries=raw_ad.get("countries", []),
                    )

        ads = list(seen.values())
        output = MetaAdsResearchOutput(
            total_ads=len(ads),
            ads=ads,
            search_terms=input.search_terms,
            countries=input.countries,
        )

        # ── Persist to Supabase ──────────────────────────────────────
        try:
            supabase = get_supabase()
            supabase.table("research_results").insert(
                {
                    "user_id": ctx.user_id,
                    "skill": SKILL_NAME,
                    "request_id": ctx.request_id,
                    "input_params": input.model_dump(),
                    "result": output.model_dump(),
                }
            ).execute()
        except Exception:
            logger.exception("Failed to persist research results to Supabase")

        # ── Cache result ─────────────────────────────────────────────
        await cache.set_cached(ctx.user_id, cache_params, output.model_dump())

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return SkillResult(
            success=True,
            data=output,
            cached=False,
            execution_ms=elapsed_ms,
        )
