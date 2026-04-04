import logging
import time

from core.errors import InvalidParamsError
from core.skill_interface import BaseSkill, SkillContext, SkillResult
from core.supabase_client import get_supabase

from SKILLS.C_product_scorer.schemas import (
    ProductScorerInput,
    ProductScorerOutput,
    ScoredProduct,
)

logger = logging.getLogger(__name__)

SKILL_NAME = "product-scorer"


# ── Scoring formula ──────────────────────────────────────────────────


def score_product(item: dict, params: dict) -> int:
    score = 0

    # Base confidence score (0-40)
    score += int(item.get("confidence", 0) * 40)

    # Source-specific scoring
    if item.get("source") == "tiktok_shop":
        sold = item.get("sold_count", 0)
        rating = item.get("rating", 0)
        trust = item.get("trust_label")
        score += int(
            min(sold / 10000, 20)
            + (rating / 5) * 10
            + (5 if trust == "best_seller" else 0)
        )
    elif item.get("source") == "meta_ads":
        days = item.get("days_running", 0)
        d = min(50, days * 1.5) + (10 if days > 30 else 0) + (5 if days > 60 else 0)
        score += int(min(d, 35))

    # EU market fit bonus
    if item.get("eu_market_fit"):
        score += 5

    # Gender match bonus
    pg = params.get("gender")
    ig = item.get("gender")
    if pg and ig and (pg == ig or ig == "unisex"):
        score += 10

    # Creator video virality bonus
    cv = item.get("creator_video") or {}
    plays = cv.get("stats", {}).get("plays", 0) if cv else 0
    if plays > 10_000_000:
        score += 15
    elif plays > 1_000_000:
        score += 10
    elif plays > 100_000:
        score += 5

    return min(score, 100)


# ── Gender filter ────────────────────────────────────────────────────


def apply_gender_filter(items: list[dict], gender: str | None) -> list[dict]:
    if gender == "woman":
        return [i for i in items if i.get("gender") != "man"]
    if gender == "man":
        return [i for i in items if i.get("gender") != "woman"]
    return items


# ── Skill class ──────────────────────────────────────────────────────


class ProductScorerSkill(BaseSkill[ProductScorerInput, ProductScorerOutput]):
    name = SKILL_NAME
    version = "1.0.0"
    description = "Scores and ranks products based on multiple signals"
    consumes_credits = False
    credit_cost = 0

    def validate(self, input: ProductScorerInput) -> bool:
        if not input.items:
            raise InvalidParamsError(
                message="items must not be empty",
                skill=SKILL_NAME,
                code="INVALID_PARAMS",
            )
        return True

    async def run(
        self, input: ProductScorerInput, ctx: SkillContext
    ) -> SkillResult[ProductScorerOutput]:
        start = time.perf_counter()
        self.validate(input)

        total_input = len(input.items)
        params = input.params

        # ── Step 1: Gender filter (HARD) ─────────────────────────────
        gender = params.get("gender")
        filtered = apply_gender_filter(input.items, gender)
        gender_filter_applied = gender is not None and len(filtered) != total_input

        # ── Step 2: Fashion + confidence filter ──────────────────────
        filtered = [
            i for i in filtered
            if i.get("is_fashion") is True and i.get("confidence", 0) >= 0.7
        ]
        total_after_filter = len(filtered)

        # ── Step 3: Score each product ───────────────────────────────
        scored_items: list[tuple[int, dict]] = []
        for item in filtered:
            s = score_product(item, params)

            # Build breakdown
            breakdown = {
                "confidence": int(item.get("confidence", 0) * 40),
                "source_signal": 0,
                "eu_market_fit": 5 if item.get("eu_market_fit") else 0,
                "gender_match": 0,
                "creator_virality": 0,
            }

            # Recalculate source signal for breakdown
            if item.get("source") == "tiktok_shop":
                sold = item.get("sold_count", 0)
                rating = item.get("rating", 0)
                trust = item.get("trust_label")
                breakdown["source_signal"] = int(
                    min(sold / 10000, 20)
                    + (rating / 5) * 10
                    + (5 if trust == "best_seller" else 0)
                )
            elif item.get("source") == "meta_ads":
                days = item.get("days_running", 0)
                d = min(50, days * 1.5) + (10 if days > 30 else 0) + (5 if days > 60 else 0)
                breakdown["source_signal"] = int(min(d, 35))

            pg = params.get("gender")
            ig = item.get("gender")
            if pg and ig and (pg == ig or ig == "unisex"):
                breakdown["gender_match"] = 10

            cv = item.get("creator_video") or {}
            plays = cv.get("stats", {}).get("plays", 0) if cv else 0
            if plays > 10_000_000:
                breakdown["creator_virality"] = 15
            elif plays > 1_000_000:
                breakdown["creator_virality"] = 10
            elif plays > 100_000:
                breakdown["creator_virality"] = 5

            scored_items.append((s, item, breakdown))

        # ── Step 4: Sort descending and take top n ───────────────────
        scored_items.sort(key=lambda x: x[0], reverse=True)
        top_items = scored_items[: input.n_results]

        products = [
            ScoredProduct(
                item_id=item.get("item_id", ""),
                score=s,
                title=item.get("title", ""),
                image_url=item.get("image_url", ""),
                product_url=item.get("product_url", ""),
                price=item.get("price", 0.0),
                currency=item.get("currency", "USD"),
                country=item.get("country", ""),
                source=item.get("source", ""),
                sold_count=item.get("sold_count"),
                rating=item.get("rating"),
                trust_label=item.get("trust_label"),
                category=item.get("category", ""),
                gender=item.get("gender", "unisex"),
                eu_market_fit=item.get("eu_market_fit", False),
                creator_video=item.get("creator_video"),
                score_breakdown=bd,
            )
            for s, item, bd in top_items
        ]

        output = ProductScorerOutput(
            total_input=total_input,
            total_after_filter=total_after_filter,
            total_returned=len(products),
            products=products,
            gender_filter_applied=gender_filter_applied,
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
                    "items_count": output.total_returned,
                }
            ).execute()
        except Exception:
            logger.exception("Failed to persist scorer results to Supabase")

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return SkillResult(
            success=True,
            data=output,
            cached=False,
            execution_ms=elapsed_ms,
        )
