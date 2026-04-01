"""Redis caching layer for Kalodata research results."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from core.redis_client import get_redis

logger = logging.getLogger(__name__)

_TTL_SECONDS = 7200  # 2 hours


def _build_key(user_id: str, params: dict[str, Any]) -> str:
    """Build a deterministic cache key from user id and query parameters."""
    raw = json.dumps(params, sort_keys=True, default=str)
    digest = hashlib.md5(raw.encode()).hexdigest()
    return f"kalodata:{user_id}:{digest}"


async def get_cached(user_id: str, params: dict[str, Any]) -> dict[str, Any] | None:
    """Return cached research output or None."""
    r = await get_redis()
    key = _build_key(user_id, params)
    cached = await r.get(key)
    if cached is None:
        return None
    logger.debug("Cache hit for key=%s", key)
    return json.loads(cached)


async def set_cached(user_id: str, params: dict[str, Any], data: dict[str, Any]) -> None:
    """Store research output in Redis with a 2-hour TTL."""
    r = await get_redis()
    key = _build_key(user_id, params)
    await r.set(key, json.dumps(data, default=str), ex=_TTL_SECONDS)
    logger.debug("Cached key=%s ttl=%ds", key, _TTL_SECONDS)
