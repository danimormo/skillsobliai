# kalodata-ripper: No cache layer needed.
#
# This skill performs write operations (downloading videos and uploading
# them to Supabase Storage), so caching results would be inappropriate.
# These passthrough functions are provided for interface consistency
# with other skills.


async def get_cached(user_id: str, params: dict) -> dict | None:
    """Always returns None -- caching is disabled for this skill."""
    return None


async def set_cached(user_id: str, params: dict, data: dict) -> None:
    """No-op -- caching is disabled for this skill."""
    pass
