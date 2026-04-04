import logging
import time
import uuid

from core.errors import InvalidParamsError, UpstreamError
from core.skill_interface import BaseSkill, SkillContext, SkillResult
from core.supabase_client import get_supabase

from SKILLS.pdp_builder import api_client, cache
from SKILLS.pdp_builder.schemas import (
    PDPBuilderInput,
    PDPBuilderOutput,
    PDPSections,
)

logger = logging.getLogger(__name__)

SKILL_NAME = "pdp-builder"


class PDPBuilderSkill(BaseSkill[PDPBuilderInput, PDPBuilderOutput]):
    name = SKILL_NAME
    version = "1.0.0"
    description = "Generate PDP copy via OpenRouter/DeepSeek"
    consumes_credits = True
    credit_cost = 1

    def validate(self, input: PDPBuilderInput) -> bool:
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
        return True

    async def run(
        self, input: PDPBuilderInput, ctx: SkillContext
    ) -> SkillResult[PDPBuilderOutput]:
        start = time.perf_counter()
        self.validate(input)

        # -- Check cache --------------------------------------------------
        cache_params = input.model_dump()
        cached_data = await cache.get_cached(ctx.user_id, cache_params)
        if cached_data is not None:
            output = PDPBuilderOutput(**cached_data)
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return SkillResult(
                success=True,
                data=output,
                cached=True,
                execution_ms=elapsed_ms,
            )

        # -- Generate PDP via OpenRouter ----------------------------------
        raw = await api_client.generate_pdp(
            product_title=input.product_title,
            product_description=input.product_description,
            price=input.price,
            original_price=input.original_price,
            category=input.category,
            copy_angle=input.copy_angle,
            target_audience=input.target_audience,
            language=input.language,
        )

        sections = PDPSections(
            headlines=raw.get("headlines", []),
            subheadline=raw.get("subheadline", ""),
            benefit_bullets=raw.get("benefit_bullets", []),
            description_long=raw.get("description_long", ""),
            faq=raw.get("faq", []),
            urgency_text=raw.get("urgency_text", ""),
            cta_text=raw.get("cta_text", ""),
        )

        # Count words across all text fields
        all_text = " ".join(
            [
                " ".join(sections.headlines),
                sections.subheadline,
                " ".join(sections.benefit_bullets),
                sections.description_long,
                sections.urgency_text,
                sections.cta_text,
            ]
        )
        word_count = len(all_text.split())

        pdp_id = str(uuid.uuid4())
        output = PDPBuilderOutput(
            pdp_id=pdp_id,
            sections=sections,
            copy_angle=input.copy_angle,
            language=input.language,
            word_count=word_count,
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
                    "items_count": word_count,
                }
            ).execute()
        except Exception:
            logger.exception("Failed to persist PDP results to Supabase")

        # -- Cache result -------------------------------------------------
        await cache.set_cached(ctx.user_id, cache_params, output.model_dump())

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return SkillResult(
            success=True,
            data=output,
            cached=False,
            execution_ms=elapsed_ms,
        )
