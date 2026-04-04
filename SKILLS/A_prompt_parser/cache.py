import hashlib
import json
import logging

from core.redis_client import get_redis

logger = logging.getLogger(__name__)

TTL_SECONDS = 1800  # 30 minutes


def _build_key(prompt: str) -> str:
    digest = hashlib.sha256(prompt.encode()).hexdigest()
    return f"parser:{digest}"


async def get_cached(prompt: str) -> dict | None:
    """Return cached parsed result or None on miss."""
    redis = await get_redis()
    key = _build_key(prompt)
    raw = await redis.get(key)
    if raw is None:
        return None
    logger.debug("Cache hit for key %s", key)
    return json.loads(raw)


async def set_cached(prompt: str, data: dict) -> None:
    """Store parsed result in Redis with TTL."""
    redis = await get_redis()
    key = _build_key(prompt)
    await redis.set(key, json.dumps(data, default=str), ex=TTL_SECONDS)
    logger.debug("Cached key %s (TTL %ds)", key, TTL_SECONDS)
