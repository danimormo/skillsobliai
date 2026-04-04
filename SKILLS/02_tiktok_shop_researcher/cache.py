"""Redis caching for TikTok Shop research results."""

from __future__ import annotations

import hashlib
import json
import logging

from core.redis_client import get_redis

logger = logging.getLogger(__name__)

TTL_SECONDS = 7200  # 2 hours


def _cache_key(params: dict) -> str:
    """Deterministic cache key from request params."""
    payload = json.dumps(sorted(params.items()), sort_keys=True)
    digest = hashlib.sha256(payload.encode()).hexdigest()
    return f"tiktok-shop:{digest}"


async def get_cached(params: dict) -> dict | None:
    """Return cached result or None."""
    try:
        r = await get_redis()
        raw = await r.get(_cache_key(params))
        if raw:
            logger.debug("Cache HIT for tiktok-shop")
            return json.loads(raw)
    except Exception:
        logger.warning("Redis read failed, skipping cache", exc_info=True)
    return None


async def set_cached(params: dict, data: dict) -> None:
    """Store result in cache with TTL."""
    try:
        r = await get_redis()
        await r.set(_cache_key(params), json.dumps(data), ex=TTL_SECONDS)
    except Exception:
        logger.warning("Redis write failed, skipping cache", exc_info=True)
