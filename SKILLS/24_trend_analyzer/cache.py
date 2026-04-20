"""Redis-backed cache with per-provider TTL.

The provider name drives both the Redis key namespace and the TTL. Keeping
everything in a single module means callers never have to remember which TTL
applies to which data source — they just ask the cache.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from core.redis_client import get_redis

logger = logging.getLogger(__name__)


# ── TTL matrix (seconds) ───────────────────────────────────────────────────

TTL_BY_PROVIDER: dict[str, int] = {
    "google_trends": 24 * 3600,
    "meta_ads": 12 * 3600,
    "tiktok": 6 * 3600,
    "shopify_saturation": 24 * 3600,
    "aliexpress": 48 * 3600,
    "google_shopping": 24 * 3600,
    "reddit": 12 * 3600,
    "youtube": 12 * 3600,
    "fingerprint": 24 * 3600,
}

# LLM creative outputs are NEVER cached — fresh generation each run.
NEVER_CACHE: set[str] = {"creatives", "llm"}

KEY_PREFIX = "trend_analyzer"


def _build_key(provider: str, payload: str) -> str:
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]
    return f"{KEY_PREFIX}:{provider}:{digest}"


def _normalize_payload(payload: Any) -> str:
    if isinstance(payload, str):
        return payload.strip().lower()
    return json.dumps(payload, sort_keys=True, default=str)


async def get(provider: str, payload: Any) -> Any | None:
    """Fetch cached JSON value or ``None`` on miss / never-cache provider."""
    if provider in NEVER_CACHE:
        return None
    redis = await get_redis()
    key = _build_key(provider, _normalize_payload(payload))
    raw = await redis.get(key)
    if raw is None:
        return None
    logger.debug("cache.hit provider=%s key=%s", provider, key)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("cache.corrupt key=%s — dropping", key)
        await redis.delete(key)
        return None


async def set(provider: str, payload: Any, value: Any) -> None:
    """Store JSON value under the provider namespace with its configured TTL."""
    if provider in NEVER_CACHE:
        return
    ttl = TTL_BY_PROVIDER.get(provider)
    if ttl is None:
        logger.warning("cache.unknown_provider provider=%s — skipping set", provider)
        return
    redis = await get_redis()
    key = _build_key(provider, _normalize_payload(payload))
    await redis.set(key, json.dumps(value, default=str), ex=ttl)
    logger.debug("cache.set provider=%s key=%s ttl=%ds", provider, key, ttl)


async def get_stale(provider: str, payload: Any) -> Any | None:
    """Return the value regardless of TTL — useful as emergency fallback.

    Redis automatically removes expired keys so "stale" here means the value
    is still present (Redis has not yet evicted it). Prefer this over a hard
    failure when an upstream provider is down.
    """
    return await get(provider, payload)


async def invalidate(provider: str, payload: Any) -> None:
    redis = await get_redis()
    key = _build_key(provider, _normalize_payload(payload))
    await redis.delete(key)
    logger.debug("cache.invalidate key=%s", key)
