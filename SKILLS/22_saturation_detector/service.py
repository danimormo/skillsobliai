import asyncio
import json
import logging
import random
import time
from pathlib import Path

import httpx
from rapidfuzz import fuzz

from core.errors import InvalidParamsError
from core.skill_interface import BaseSkill, SkillContext, SkillResult

from SKILLS.saturation_detector import api_client, cache
from SKILLS.saturation_detector.schemas import (
    SaturationDetectorInput,
    SaturationDetectorOutput,
)

logger = logging.getLogger(__name__)

SKILL_NAME = "saturation-detector"
BATCH_SIZE = 20
BATCH_DELAY_S = 0.2
MATCH_THRESHOLD = 80

DATA_DIR = Path(__file__).parent / "data"


def _load_store_list() -> list[str]:
    """Load Shopify store domains from the sample stores JSON file."""
    stores_file = DATA_DIR / "shopify_sample_stores.json"
    if not stores_file.exists():
        logger.warning("Store list file not found at %s", stores_file)
        return []
    with open(stores_file) as f:
        return json.load(f)


def _matches_product(
    product_title: str,
    product_keywords: list[str],
    store_product_title: str,
) -> bool:
    """Check if a store product matches the target product by title or keywords."""
    if fuzz.token_sort_ratio(product_title.lower(), store_product_title.lower()) >= MATCH_THRESHOLD:
        return True
    for keyword in product_keywords:
        if fuzz.token_sort_ratio(keyword.lower(), store_product_title.lower()) >= MATCH_THRESHOLD:
            return True
    return False


def _classify(saturation_index: float) -> tuple[str, str]:
    """Return (saturation_level, flag) based on the saturation index."""
    if saturation_index < 0.05:
        return "low", "green"
    elif saturation_index < 0.15:
        return "medium", "yellow"
    elif saturation_index < 0.30:
        return "high", "red"
    else:
        return "very_high", "red"


def _build_recommendation(level: str, saturation_index: float) -> str:
    pct = round(saturation_index * 100, 1)
    if level == "low":
        return (
            f"Low saturation ({pct}%). This product has minimal competition "
            "on Shopify stores. Good opportunity to enter the market."
        )
    elif level == "medium":
        return (
            f"Medium saturation ({pct}%). Some stores already sell this product. "
            "You can still compete with strong branding and creative angles."
        )
    elif level == "high":
        return (
            f"High saturation ({pct}%). Many stores carry this product. "
            "Consider differentiating heavily or finding a unique niche."
        )
    else:
        return (
            f"Very high saturation ({pct}%). This product is extremely common. "
            "Entering this market is risky without a very strong unique selling proposition."
        )


class SaturationDetectorSkill(BaseSkill[SaturationDetectorInput, SaturationDetectorOutput]):
    name = SKILL_NAME
    version = "1.0.0"
    description = "Check product saturation by scanning Shopify stores"
    consumes_credits = True
    credit_cost = 1

    def validate(self, input: SaturationDetectorInput) -> bool:
        if not input.product_title.strip():
            raise InvalidParamsError(
                message="product_title must not be empty",
                skill=SKILL_NAME,
                code="INVALID_PARAMS",
            )
        return True

    async def run(
        self, input: SaturationDetectorInput, ctx: SkillContext
    ) -> SkillResult[SaturationDetectorOutput]:
        start = time.perf_counter()
        self.validate(input)

        # ── Check cache ──────────────────────────────────────────────
        cached_data = await cache.get_cached(input.product_title)
        if cached_data is not None:
            output = SaturationDetectorOutput(**cached_data)
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return SkillResult(
                success=True,
                data=output,
                cached=True,
                execution_ms=elapsed_ms,
            )

        # ── Load and sample stores ───────────────────────────────────
        all_stores = _load_store_list()
        if not all_stores:
            raise InvalidParamsError(
                message="No store list available for saturation check",
                skill=SKILL_NAME,
                code="NO_STORE_LIST",
            )

        sample_size = min(input.sample_size, len(all_stores))
        sampled_stores = random.sample(all_stores, sample_size)

        # ── Scan stores in batches ───────────────────────────────────
        found_in_stores: list[str] = []

        async with httpx.AsyncClient(
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0"},
        ) as client:
            for batch_start in range(0, len(sampled_stores), BATCH_SIZE):
                batch = sampled_stores[batch_start : batch_start + BATCH_SIZE]

                tasks = [
                    api_client.fetch_store_products(client, domain)
                    for domain in batch
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for domain, result in zip(batch, results):
                    if isinstance(result, Exception):
                        logger.debug("Skipping store %s: %s", domain, result)
                        continue
                    for product in result:
                        title = product.get("title", "")
                        if _matches_product(input.product_title, input.product_keywords, title):
                            found_in_stores.append(domain)
                            break

                # Delay between batches to avoid overwhelming stores
                if batch_start + BATCH_SIZE < len(sampled_stores):
                    await asyncio.sleep(BATCH_DELAY_S)

        # ── Calculate results ────────────────────────────────────────
        stores_found = len(found_in_stores)
        saturation_index = stores_found / sample_size if sample_size > 0 else 0.0
        level, flag = _classify(saturation_index)
        recommendation = _build_recommendation(level, saturation_index)

        output = SaturationDetectorOutput(
            product_title=input.product_title,
            stores_found=stores_found,
            stores_sampled=sample_size,
            saturation_index=round(saturation_index, 4),
            saturation_level=level,
            flag=flag,
            recommendation=recommendation,
            found_in_stores=found_in_stores,
        )

        # ── Cache result ─────────────────────────────────────────────
        await cache.set_cached(input.product_title, output.model_dump())

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return SkillResult(
            success=True,
            data=output,
            cached=False,
            execution_ms=elapsed_ms,
        )
