import json
import logging

import anthropic

from core.config import settings
from core.errors import UpstreamError

logger = logging.getLogger(__name__)

SKILL_NAME = "creative-ideator"

SYSTEM_PROMPT = (
    "You are a direct response creative strategist specializing in Meta and TikTok ads. "
    "Generate creative briefs for e-commerce products. Respond ONLY with valid JSON. "
    "No markdown, no explanations."
)


async def generate_with_claude(system_prompt: str, user_prompt: str) -> str:
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = await client.messages.create(
        model=settings.ANTHROPIC_MODEL_QUALITY,
        max_tokens=2000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return response.content[0].text


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
    """Call Anthropic Claude to generate creative angles.

    Returns a dict with keys: angles (list), recommended_angle (str).
    """
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

    user_prompt = "\n".join(user_prompt_parts)

    try:
        content = await generate_with_claude(SYSTEM_PROMPT, user_prompt)
        return json.loads(content)
    except anthropic.AuthenticationError as exc:
        raise UpstreamError(
            message=f"Invalid Anthropic API key: {exc}",
            skill=SKILL_NAME,
            code="INVALID_API_KEY",
        )
    except anthropic.APIError as exc:
        raise UpstreamError(
            message=f"Anthropic API error: {exc}",
            skill=SKILL_NAME,
            code="UPSTREAM_ERROR",
        )
    except (json.JSONDecodeError, IndexError, KeyError) as exc:
        raise UpstreamError(
            message=f"Failed to parse Claude response: {exc}",
            skill=SKILL_NAME,
            code="UPSTREAM_ERROR",
        )
