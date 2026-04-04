"""TikTok Shop Researcher skill -- service layer."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from core.config import settings
from core.errors import UpstreamError
from core.skill_interface import BaseSkill, SkillContext, SkillResult
from core.supabase_client import get_supabase

from .api_client import search_tiktok_shop
from .cache import get_cached, set_cached
from .schemas import TikTokShopInput, TikTokShopOutput, TikTokShopProduct

logger = logging.getLogger(__name__)

# ── Currency map ────────────────────────────────────────────────────────────

CURRENCY_MAP: dict[str, str] = {
    "US": "USD",
    "GB": "GBP",
    "DE": "EUR",
    "FR": "EUR",
    "IT": "EUR",
    "ES": "EUR",
    "IE": "EUR",
    "JP": "JPY",
    "TH": "THB",
    "ID": "IDR",
    "MY": "MYR",
    "SG": "SGD",
    "MX": "MXN",
    "VN": "VND",
    "BR": "BRL",
    "PH": "PHP",
}

# ── Keyword pools (loaded once at module level) ────────────────────────────

_KEYWORD_POOLS: dict[str, list[str]] = {}

_pool_path = Path(__file__).resolve().parent.parent.parent / "data" / "tiktok_keyword_pools.json"
if _pool_path.exists():
    with open(_pool_path, "r", encoding="utf-8") as _f:
        _KEYWORD_POOLS = json.load(_f)
else:
    logger.warning("Keyword pool file not found at %s", _pool_path)


# ── Helpers ─────────────────────────────────────────────────────────────────


def select_keywords(
    country: str,
    n_results: int,
    keywords_by_country: dict[str, list[str]],
) -> list[str]:
    """Pick keywords for a country.

    If the caller supplied explicit keywords, use ALL of them.
    Otherwise sample from the pool based on desired result count.
    """
    if country in keywords_by_country and keywords_by_country[country]:
        return list(keywords_by_country[country])

    pool = _KEYWORD_POOLS.get(country, [])
    if not pool:
        return []

    if n_results <= 3:
        n_kw = 4
    elif n_results <= 5:
        n_kw = 6
    elif n_results <= 10:
        n_kw = 10
    else:
        n_kw = 15

    n_kw = min(n_kw, len(pool))
    return random.sample(pool, n_kw)


def _days_since(iso_date: str | None) -> int:
    """Return days since an ISO date string; defaults to 9999 if unparseable."""
    if not iso_date:
        return 9999
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).days
    except Exception:
        return 9999


def normalize_product(raw: dict, country: str) -> TikTokShopProduct:
    """Transform a raw ScrapeCreators product dict into our schema."""

    product_id = str(raw.get("id", raw.get("product_id", raw.get("item_id", ""))))
    title = raw.get("title", raw.get("name", ""))
    image_url = raw.get("image_url", raw.get("cover", raw.get("thumbnail", "")))

    # ── Price (centesimi fix) ───────────────────────────────────────────
    raw_price = float(raw.get("price", raw.get("sale_price", 0)))
    price = raw_price / 100 if raw_price > 500 else raw_price

    # ── Country resolution: ship_from > seller_info.region > fallback ──
    seller_info = raw.get("seller_info", {}) or {}
    ship_from = raw.get("ship_from", "")
    seller_region = seller_info.get("region", "")
    resolved_country = ship_from or seller_region or country

    # If resolved contains a CDN-EU hint, fall back to the input country
    if "tiktokcdn-eu" in str(resolved_country).lower():
        resolved_country = country

    # Ensure we use the 2-letter code
    if len(resolved_country) != 2:
        resolved_country = country

    currency = CURRENCY_MAP.get(resolved_country.upper(), "USD")

    # ── Sold count & rating ─────────────────────────────────────────────
    sold_count = int(raw.get("sold_count", raw.get("sold", raw.get("sales", 0))))
    rating = float(raw.get("rating", raw.get("star", 0)))

    # ── Creator video extraction ────────────────────────────────────────
    creator_video: dict | None = None
    cv_raw = raw.get("creator_video") or raw.get("video")
    if cv_raw and isinstance(cv_raw, dict):
        author = cv_raw.get("author", {}) or {}
        stats = cv_raw.get("stats", cv_raw.get("statistics", {})) or {}
        creator_video = {
            "author": {
                "unique_id": author.get("unique_id", author.get("uniqueId", "")),
                "nickname": author.get("nickname", ""),
                "avatar": author.get("avatar", author.get("avatarThumb", "")),
            },
            "stats": {
                "play_count": stats.get("play_count", stats.get("playCount", 0)),
                "like_count": stats.get("like_count", stats.get("diggCount", 0)),
                "share_count": stats.get("share_count", stats.get("shareCount", 0)),
                "comment_count": stats.get("comment_count", stats.get("commentCount", 0)),
            },
        }

    # ── Velocity signal ─────────────────────────────────────────────────
    if sold_count > 10_000:
        velocity_signal = "high"
    elif sold_count > 1_000:
        velocity_signal = "medium"
    else:
        velocity_signal = "low"

    # ── Trust label ─────────────────────────────────────────────────────
    raw_label = str(raw.get("label", raw.get("trust_label", ""))).lower()
    if sold_count > 10_000 or "best_seller" in raw_label or "best seller" in raw_label:
        trust_label = "best_seller"
    elif "new_arrival" in raw_label or "new arrival" in raw_label:
        trust_label = "new_arrival"
    else:
        trust_label = None

    new_arrival = trust_label == "new_arrival" or "new" in raw_label

    seo_url_updated_at = raw.get("seo_url_updated_at", raw.get("updated_at"))

    product_url = raw.get("product_url", raw.get("url", ""))

    return TikTokShopProduct(
        item_id=f"tiktok_{product_id}",
        title=title,
        image_url=image_url,
        product_url=product_url,
        price=price,
        currency=currency,
        country=resolved_country.upper(),
        sold_count=sold_count,
        rating=rating,
        trust_label=trust_label,
        creator_video=creator_video,
        velocity_signal=velocity_signal,
        new_arrival=new_arrival,
        seo_url_updated_at=seo_url_updated_at,
    )


def filter_products(
    products: list[TikTokShopProduct],
    n_results: int,
) -> tuple[list[TikTokShopProduct], int]:
    """Progressive tier filtering (T1-T5). Returns (filtered list, tier used)."""

    def _revenue(p: TikTokShopProduct) -> float:
        return p.price * p.sold_count

    def _days(p: TikTokShopProduct) -> int:
        return _days_since(p.seo_url_updated_at)

    tiers: list[tuple[int, callable]] = [
        (1, lambda p: 89_000 <= _revenue(p) <= 120_000 and _days(p) <= 30),
        (2, lambda p: 50_000 <= _revenue(p) <= 150_000 and _days(p) <= 45),
        (3, lambda p: 20_000 <= _revenue(p) <= 200_000 and _days(p) <= 60),
        (4, lambda p: 1 <= p.price <= 150 and p.sold_count >= 500),
        (5, lambda p: True),
    ]

    for tier_num, predicate in tiers:
        filtered = [p for p in products if predicate(p)]
        if len(filtered) >= 3:
            # Sort by revenue descending, take top n_results
            filtered.sort(key=lambda p: _revenue(p), reverse=True)
            return filtered[:n_results], tier_num

    # Fallback: return everything (T5)
    products_sorted = sorted(products, key=lambda p: _revenue(p), reverse=True)
    return products_sorted[:n_results], 5


# ── Skill class ─────────────────────────────────────────────────────────────


class TikTokShopResearcherSkill(BaseSkill[TikTokShopInput, TikTokShopOutput]):
    name = "tiktok-shop-researcher"
    version = "2.0.0"
    description = "Discover trending TikTok Shop products via ScrapeCreators API."

    async def run(
        self, input: TikTokShopInput, ctx: SkillContext
    ) -> SkillResult[TikTokShopOutput]:
        t0 = time.perf_counter()

        # ── Check cache ─────────────────────────────────────────────────
        cache_params = {
            "countries": sorted(input.countries),
            "keywords_by_country": {
                k: sorted(v) for k, v in input.keywords_by_country.items()
            },
            "n_results": input.n_results,
        }
        cached = await get_cached(cache_params)
        if cached:
            return SkillResult(
                success=True,
                data=TikTokShopOutput(**cached),
                cached=True,
                execution_ms=int((time.perf_counter() - t0) * 1000),
            )

        # ── Build keyword map per country ───────────────────────────────
        fetch_limit = input.fetch_limit or max(50, input.n_results * 10)

        countries_searched: list[str] = []
        countries_skipped: list[str] = []

        # Collect all (country, keyword) pairs
        tasks: list[tuple[str, str]] = []
        for country in input.countries:
            if country.upper() == "IE":
                logger.warning("Skipping IE -- not supported by ScrapeCreators")
                countries_skipped.append("IE")
                continue
            kws = select_keywords(country, input.n_results, input.keywords_by_country)
            if not kws:
                countries_skipped.append(country)
                continue
            countries_searched.append(country)
            for kw in kws:
                tasks.append((country, kw))

        # ── Batch API calls in groups of 5 with 200ms delay ────────────
        all_raw: list[tuple[str, dict]] = []

        async with httpx.AsyncClient(timeout=30) as client:
            for batch_start in range(0, len(tasks), 5):
                batch = tasks[batch_start : batch_start + 5]

                async def _fetch(country: str, keyword: str) -> list[tuple[str, dict]]:
                    try:
                        products = await search_tiktok_shop(keyword, country, client)
                        return [(country, p) for p in products]
                    except Exception:
                        logger.warning(
                            "Failed to fetch keyword=%s country=%s",
                            keyword,
                            country,
                            exc_info=True,
                        )
                        return []

                coros = [_fetch(c, kw) for c, kw in batch]
                results = await asyncio.gather(*coros)
                for chunk in results:
                    all_raw.extend(chunk)

                # Enforce fetch_limit early
                if len(all_raw) >= fetch_limit:
                    all_raw = all_raw[:fetch_limit]
                    break

                # 200ms delay between batches (skip after last)
                if batch_start + 5 < len(tasks):
                    await asyncio.sleep(0.2)

        # ── Normalize ───────────────────────────────────────────────────
        normalized: list[TikTokShopProduct] = []
        for country, raw_product in all_raw:
            try:
                normalized.append(normalize_product(raw_product, country))
            except Exception:
                logger.debug("Failed to normalize product", exc_info=True)

        # ── Deduplicate by item_id ──────────────────────────────────────
        seen: set[str] = set()
        unique: list[TikTokShopProduct] = []
        for p in normalized:
            if p.item_id not in seen:
                seen.add(p.item_id)
                unique.append(p)

        total_fetched = len(unique)

        # ── Filter ──────────────────────────────────────────────────────
        filtered, tier_used = filter_products(unique, input.n_results)
        total_after_filter = len(filtered)

        output = TikTokShopOutput(
            total_fetched=total_fetched,
            total_after_filter=total_after_filter,
            products=filtered,
            countries_searched=countries_searched,
            countries_skipped=countries_skipped,
            filter_tier_used=tier_used,
        )

        # ── Save to Supabase ────────────────────────────────────────────
        try:
            sb = get_supabase()
            rows = [
                {
                    "user_id": ctx.user_id,
                    "request_id": ctx.request_id,
                    "skill": self.name,
                    "item_id": p.item_id,
                    "payload": p.model_dump(),
                }
                for p in filtered
            ]
            if rows:
                sb.table("research_results").insert(rows).execute()
        except Exception:
            logger.warning("Failed to save research_results", exc_info=True)

        # ── Cache result ────────────────────────────────────────────────
        await set_cached(cache_params, output.model_dump())

        elapsed = int((time.perf_counter() - t0) * 1000)
        return SkillResult(
            success=True,
            data=output,
            execution_ms=elapsed,
        )
