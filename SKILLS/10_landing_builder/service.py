import logging
import time
import uuid

from core.errors import InvalidParamsError, UpstreamError
from core.skill_interface import BaseSkill, SkillContext, SkillResult
from core.supabase_client import get_supabase

from SKILLS.landing_builder import api_client, cache
from SKILLS.landing_builder.schemas import (
    LandingBuilderInput,
    LandingBuilderOutput,
    LandingSection,
)

logger = logging.getLogger(__name__)

SKILL_NAME = "landing-builder"


class LandingBuilderSkill(BaseSkill[LandingBuilderInput, LandingBuilderOutput]):
    name = SKILL_NAME
    version = "1.0.0"
    description = "Generate landing page copy via OpenRouter/DeepSeek"
    consumes_credits = True
    credit_cost = 1

    def validate(self, input: LandingBuilderInput) -> bool:
        if not input.product_title.strip():
            raise InvalidParamsError(
                message="product_title must not be empty",
                skill=SKILL_NAME,
                code="INVALID_PARAMS",
            )
        if input.price <= 0:
            raise InvalidParamsError(
                message="price must be positive",
                skill=SKILL_NAME,
                code="INVALID_PARAMS",
            )
        if not input.cta_destination_url.strip():
            raise InvalidParamsError(
                message="cta_destination_url must not be empty",
                skill=SKILL_NAME,
                code="INVALID_PARAMS",
            )
        return True

    async def run(
        self, input: LandingBuilderInput, ctx: SkillContext
    ) -> SkillResult[LandingBuilderOutput]:
        start = time.perf_counter()
        self.validate(input)

        # -- Check cache --------------------------------------------------
        cache_params = input.model_dump()
        cached_data = await cache.get_cached(ctx.user_id, cache_params)
        if cached_data is not None:
            output = LandingBuilderOutput(**cached_data)
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return SkillResult(
                success=True,
                data=output,
                cached=True,
                execution_ms=elapsed_ms,
            )

        # -- Generate landing via OpenRouter ------------------------------
        raw_sections = await api_client.generate_landing(
            product_title=input.product_title,
            product_description=input.product_description,
            price=input.price,
            original_price=input.original_price,
            target_audience=input.target_audience,
            main_benefit=input.main_benefit,
            cta_destination_url=input.cta_destination_url,
            language=input.language,
        )

        sections = [
            LandingSection(
                type=s.get("type", "unknown"),
                headline=s.get("headline", ""),
                body=s.get("body", ""),
                cta_text=s.get("cta_text"),
            )
            for s in raw_sections
        ]

        # Count total words
        all_text = " ".join(
            f"{s.headline} {s.body} {s.cta_text or ''}" for s in sections
        )
        total_word_count = len(all_text.split())

        landing_id = str(uuid.uuid4())
        output = LandingBuilderOutput(
            landing_id=landing_id,
            sections=sections,
            total_word_count=total_word_count,
            language=input.language,
        )

        # -- Persist to Supabase ------------------------------------------
        try:
            supabase = get_supabase()
            supabase.table("research_results").insert(
                {
                    "user_id": ctx.user_id,
                    "skill": SKILL_NAME,
                    "query_params": input.model_dump(),
                    "result": output.model_dump(),
                    "items_count": len(sections),
                }
            ).execute()
        except Exception:
            logger.exception("Failed to persist landing results to Supabase")

        # -- Cache result -------------------------------------------------
        await cache.set_cached(ctx.user_id, cache_params, output.model_dump())

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return SkillResult(
            success=True,
            data=output,
            cached=False,
            execution_ms=elapsed_ms,
        )
