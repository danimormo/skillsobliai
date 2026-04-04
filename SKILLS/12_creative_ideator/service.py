import logging
import time

from core.errors import InvalidParamsError, UpstreamError
from core.skill_interface import BaseSkill, SkillContext, SkillResult
from core.supabase_client import get_supabase

from SKILLS.creative_ideator import api_client, cache
from SKILLS.creative_ideator.schemas import (
    CreativeAngle,
    CreativeIdeatorInput,
    CreativeIdeatorOutput,
)

logger = logging.getLogger(__name__)

SKILL_NAME = "creative-ideator"


class CreativeIdeatorSkill(
    BaseSkill[CreativeIdeatorInput, CreativeIdeatorOutput]
):
    name = SKILL_NAME
    version = "1.0.0"
    description = "Generate creative briefs and ad angles via OpenRouter/DeepSeek"
    consumes_credits = True
    credit_cost = 1

    def validate(self, input: CreativeIdeatorInput) -> bool:
        if not input.product_title.strip():
            raise InvalidParamsError(
                message="product_title must not be empty",
                skill=SKILL_NAME,
                code="INVALID_PARAMS",
            )
        if not input.product_description.strip():
            raise InvalidParamsError(
                message="product_description must not be empty",
                skill=SKILL_NAME,
                code="INVALID_PARAMS",
            )
        if input.num_angles < 1 or input.num_angles > 10:
            raise InvalidParamsError(
                message="num_angles must be between 1 and 10",
                skill=SKILL_NAME,
                code="INVALID_PARAMS",
            )
        return True

    async def run(
        self, input: CreativeIdeatorInput, ctx: SkillContext
    ) -> SkillResult[CreativeIdeatorOutput]:
        start = time.perf_counter()
        self.validate(input)

        # -- Check cache --------------------------------------------------
        cache_params = input.model_dump()
        cached_data = await cache.get_cached(ctx.user_id, cache_params)
        if cached_data is not None:
            output = CreativeIdeatorOutput(**cached_data)
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return SkillResult(
                success=True,
                data=output,
                cached=True,
                execution_ms=elapsed_ms,
            )

        # -- Generate creative angles via OpenRouter ----------------------
        raw = await api_client.generate_creative_angles(
            product_title=input.product_title,
            product_description=input.product_description,
            category=input.category,
            target_audience=input.target_audience,
            price=input.price,
            competitor_hooks=input.competitor_hooks,
            top_content_angles=input.top_content_angles,
            num_angles=input.num_angles,
            platform=input.platform,
            language=input.language,
        )

        raw_angles = raw.get("angles", [])
        angles = [
            CreativeAngle(
                name=a.get("name", ""),
                hook=a.get("hook", ""),
                script_30s=a.get("script_30s", ""),
                format=a.get("format", ""),
                visual_refs=a.get("visual_refs", []),
                target_emotion=a.get("target_emotion", ""),
                estimated_ctr_tier=a.get("estimated_ctr_tier", "medium"),
            )
            for a in raw_angles
        ]

        recommended_angle = raw.get("recommended_angle", "")
        if not recommended_angle and angles:
            recommended_angle = angles[0].name

        output = CreativeIdeatorOutput(
            product_title=input.product_title,
            angles=angles,
            recommended_angle=recommended_angle,
            platform=input.platform,
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
                    "items_count": len(angles),
                }
            ).execute()
        except Exception:
            logger.exception("Failed to persist creative ideator results to Supabase")

        # -- Cache result -------------------------------------------------
        await cache.set_cached(ctx.user_id, cache_params, output.model_dump())

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return SkillResult(
            success=True,
            data=output,
            cached=False,
            execution_ms=elapsed_ms,
        )
