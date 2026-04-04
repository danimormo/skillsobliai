import asyncio
import logging
import time

from core.errors import InvalidParamsError
from core.skill_interface import BaseSkill, SkillContext, SkillResult
from core.supabase_client import get_supabase

from . import api_client
from .schemas import (
    ClassifiedItem,
    ImageItem,
    VisionClassifierInput,
    VisionClassifierOutput,
)

logger = logging.getLogger(__name__)

SKILL_NAME = "vision-classifier"
BATCH_DELAY_SECONDS = 0.2


async def _classify_single(item: ImageItem) -> ClassifiedItem:
    """Classify a single image item. Returns error-safe ClassifiedItem."""
    try:
        image_b64, media_type = await api_client.download_image(item.image_url)
        result = await api_client.classify_image(image_b64, media_type, item.title)

        return ClassifiedItem(
            item_id=item.item_id,
            image_url=item.image_url,
            is_fashion=result.get("is_fashion", False),
            confidence=result.get("confidence", 0.0),
            category=result.get("category", "non_fashion"),
            subcategory=result.get("subcategory", "unknown"),
            target_gender=result.get("target_gender", "unknown"),
            gender=result.get("gender", "unisex"),
            price_tier=result.get("price_tier", "unknown"),
            style_tags=result.get("style_tags", []),
            reasoning=result.get("reasoning", ""),
            eu_market_fit=result.get("eu_market_fit", False),
            classification_error=None,
        )
    except Exception as exc:
        logger.warning("Classification failed for %s: %s", item.item_id, exc)
        return ClassifiedItem(
            item_id=item.item_id,
            image_url=item.image_url,
            is_fashion=False,
            confidence=0.0,
            category="non_fashion",
            subcategory="unknown",
            target_gender="unknown",
            gender="unisex",
            price_tier="unknown",
            style_tags=[],
            reasoning="",
            eu_market_fit=False,
            classification_error=str(exc),
        )


class VisionClassifierSkill(BaseSkill[VisionClassifierInput, VisionClassifierOutput]):
    name = SKILL_NAME
    version = "1.0.0"
    description = "Classifies product images using Claude Haiku Vision"
    consumes_credits = True
    credit_cost = 1

    def validate(self, input: VisionClassifierInput) -> bool:
        if not input.items:
            raise InvalidParamsError(
                message="items must not be empty",
                skill=SKILL_NAME,
                code="INVALID_PARAMS",
            )
        return True

    async def run(
        self, input: VisionClassifierInput, ctx: SkillContext
    ) -> SkillResult[VisionClassifierOutput]:
        start = time.perf_counter()
        self.validate(input)

        # ── Split into batches and process ───────────────────────────
        all_classified: list[ClassifiedItem] = []
        batch_size = input.batch_size or 5

        for i in range(0, len(input.items), batch_size):
            batch = input.items[i : i + batch_size]

            if i > 0:
                await asyncio.sleep(BATCH_DELAY_SECONDS)

            results = await asyncio.gather(
                *[_classify_single(item) for item in batch]
            )
            all_classified.extend(results)

        # ── Compute totals ───────────────────────────────────────────
        total_fashion = sum(1 for c in all_classified if c.is_fashion)
        total_errors = sum(1 for c in all_classified if c.classification_error is not None)

        output = VisionClassifierOutput(
            total_processed=len(all_classified),
            total_fashion=total_fashion,
            total_non_fashion=len(all_classified) - total_fashion,
            total_errors=total_errors,
            items=all_classified,
        )

        # ── Persist to Supabase ──────────────────────────────────────
        try:
            supabase = get_supabase()
            supabase.table("research_results").insert(
                {
                    "user_id": ctx.user_id,
                    "skill": SKILL_NAME,
                    "query_params": input.model_dump(),
                    "result": output.model_dump(),
                    "items_count": output.total_processed,
                }
            ).execute()
        except Exception:
            logger.exception("Failed to persist classification results to Supabase")

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return SkillResult(
            success=True,
            data=output,
            cached=False,
            execution_ms=elapsed_ms,
        )
