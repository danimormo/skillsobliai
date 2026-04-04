"""Cache module for product-importer.

This skill performs write operations (product creation), so caching is
intentionally a no-op.  The functions exist to keep the module interface
consistent with other skills.
"""

import logging

logger = logging.getLogger(__name__)


async def get_cached(user_id: str, params: dict) -> None:  # noqa: ARG001
    """Always returns None -- no caching for write operations."""
    return None


async def set_cached(user_id: str, params: dict, data: dict) -> None:  # noqa: ARG001
    """No-op -- nothing to cache for write operations."""
    return None
