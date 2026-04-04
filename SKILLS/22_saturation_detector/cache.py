import hashlib
import json
import logging

from core.redis_client import get_redis

logger = logging.getLogger(__name__)

TTL_SECONDS = 21600  # 6 hours


def _build_key(title: str) -> str:
    digest = hashlib.md5(title.encode()).hexdigest()
    return f"saturation:{digest}"


async def get_cached(title: str) -> dict | None:
    """Return cached saturation result or None if cache miss."""
    redis = await get_redis()
    key = _build_key(title)
    raw = await redis.get(key)
    if raw is None:
        return None
    logger.debug("Cache hit for key %s", key)
    return json.loads(raw)


async def set_cached(title: str, data: dict) -> None:
    """Store saturation result in Redis with TTL."""
    redis = await get_redis()
    key = _build_key(title)
    await redis.set(key, json.dumps(data, default=str), ex=TTL_SECONDS)
    logger.debug("Cached key %s (TTL %ds)", key, TTL_SECONDS)
