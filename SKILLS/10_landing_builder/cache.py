import hashlib
import json
import logging

from core.redis_client import get_redis

logger = logging.getLogger(__name__)

TTL_SECONDS = 14400  # 4 hours


def _build_key(user_id: str, params: dict) -> str:
    serialized = json.dumps(params, sort_keys=True, default=str)
    digest = hashlib.md5(serialized.encode()).hexdigest()
    return f"landing:{user_id}:{digest}"


async def get_cached(user_id: str, params: dict) -> dict | None:
    """Return cached result or None if cache miss."""
    redis = await get_redis()
    key = _build_key(user_id, params)
    raw = await redis.get(key)
    if raw is None:
        return None
    logger.debug("Cache hit for key %s", key)
    return json.loads(raw)


async def set_cached(user_id: str, params: dict, data: dict) -> None:
    """Store result in Redis with TTL."""
    redis = await get_redis()
    key = _build_key(user_id, params)
    await redis.set(key, json.dumps(data, default=str), ex=TTL_SECONDS)
    logger.debug("Cached key %s (TTL %ds)", key, TTL_SECONDS)
