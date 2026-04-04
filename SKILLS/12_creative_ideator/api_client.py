import asyncio
import json
import logging

import httpx

from core.config import settings
from core.errors import InvalidApiKeyError, UpstreamError

logger = logging.getLogger(__name__)

SKILL_NAME = "creative-ideator"
MAX_RETRIES = 3
BACKOFF_FACTORS = [1, 2, 4]

SYSTEM_PROMPT = (
    "You are a world-class performance creative strategist. "
    "Generate creative angles for paid ads as JSON."
)


async def generate_creative_angles(
    product_title: str,
    product_description: str,
    category: str | None,
    target_audience: str | None,
    price: float | None,
    competitor_hooks: list[str],
    top_content_angles: list[str],
    num_angles: int,
    platform: str,
    language: str,
) -> dict:
    """Call OpenRouter chat completions to generate creative angles.

    Retries up to 3 times on 429 / 5xx with exponential backoff.
    Returns a dict with keys: angles (list), recommended_angle (str).
    """
    url = f"{settings.OPENROUTER_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    user_prompt_parts = [
        f"Product: {product_title}",
        f"Description: {product_description}",
        f"Platform: {platform}",
        f"Number of angles: {num_angles}",
        f"Language: {language}",
    ]
    if category:
        user_prompt_parts.append(f"Category: {category}")
    if target_audience:
        user_prompt_parts.append(f"Target audience: {target_audience}")
    if price is not None:
        user_prompt_parts.append(f"Price: {price}")
    if competitor_hooks:
        user_prompt_parts.append(f"Competitor hooks: {', '.join(competitor_hooks)}")
    if top_content_angles:
        user_prompt_parts.append(
            f"Top performing content angles: {', '.join(top_content_angles)}"
        )
    user_prompt_parts.append(
        f"\nReturn a JSON object with:\n"
        f"- 'angles': list of {num_angles} objects, each with: name (str), "
        f"hook (str), script_30s (str), format (str e.g. UGC/static/carousel), "
        f"visual_refs (list[str]), target_emotion (str), "
        f"estimated_ctr_tier (str: high/medium/low)\n"
        f"- 'recommended_angle': name of the best angle"
    )

    payload = {
        "model": settings.OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "\n".join(user_prompt_parts)},
        ],
        "temperature": 0.8,
        "response_format": {"type": "json_object"},
    }

    last_exc: Exception | None = None

    async with httpx.AsyncClient(timeout=60.0) as client:
        for attempt in range(MAX_RETRIES):
            try:
                response = await client.post(url, headers=headers, json=payload)

                if response.status_code == 401:
                    raise InvalidApiKeyError(
                        message="Invalid OpenRouter API key",
                        skill=SKILL_NAME,
                        code="INVALID_API_KEY",
                    )

                if response.status_code == 429 or response.status_code >= 500:
                    wait = BACKOFF_FACTORS[attempt] if attempt < len(BACKOFF_FACTORS) else BACKOFF_FACTORS[-1]
                    logger.warning(
                        "OpenRouter %s (attempt %d/%d), retrying in %ds",
                        response.status_code,
                        attempt + 1,
                        MAX_RETRIES,
                        wait,
                    )
                    last_exc = UpstreamError(
                        message=f"Upstream returned {response.status_code}",
                        skill=SKILL_NAME,
                        code="UPSTREAM_ERROR",
                    )
                    await asyncio.sleep(wait)
                    continue

                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                return json.loads(content)

            except (httpx.ConnectError, httpx.ReadTimeout) as exc:
                wait = BACKOFF_FACTORS[attempt] if attempt < len(BACKOFF_FACTORS) else BACKOFF_FACTORS[-1]
                logger.warning(
                    "OpenRouter connection error (attempt %d/%d): %s",
                    attempt + 1,
                    MAX_RETRIES,
                    exc,
                )
                last_exc = exc
                await asyncio.sleep(wait)
                continue

    raise UpstreamError(
        message=f"OpenRouter unavailable after {MAX_RETRIES} retries: {last_exc}",
        skill=SKILL_NAME,
        code="UPSTREAM_ERROR",
    )
