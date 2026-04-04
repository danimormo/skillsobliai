# No cache for product scorer -- pure computation, no need to cache.


async def get_cached(*_args, **_kwargs) -> None:
    """Passthrough -- always returns None (no cache)."""
    return None


async def set_cached(*_args, **_kwargs) -> None:
    """Passthrough -- does nothing."""
    pass
