import json
import logging

import anthropic

from core.config import settings
from core.errors import UpstreamError

logger = logging.getLogger(__name__)

SKILL_NAME = "pdp-builder"

SYSTEM_PROMPT = (
    "You are an expert e-commerce copywriter specializing in direct response. "
    "Generate product page copy that converts. Respond ONLY with valid JSON. "
    "No markdown, no code fences, no explanations — just the JSON object."
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


async def generate_pdp(
    product_title: str,
    product_description: str | None,
    price: float,
    original_price: float | None,
    category: str | None,
    copy_angle: str,
    target_audience: str | None,
    language: str,
) -> dict:
    """Call Anthropic Claude to generate PDP copy.

    Returns a dict with PDP section data.
    """
    user_prompt_parts = [
        f"Product: {product_title}",
        f"Price: {price}",
    ]
    if product_description:
        user_prompt_parts.append(f"Description: {product_description}")
    if original_price:
        user_prompt_parts.append(f"Original price: {original_price}")
    if category:
        user_prompt_parts.append(f"Category: {category}")
    if target_audience:
        user_prompt_parts.append(f"Target audience: {target_audience}")
    user_prompt_parts.append(f"Copy angle: {copy_angle}")
    user_prompt_parts.append(f"Language: {language}")
    user_prompt_parts.append(
        "\nReturn a JSON object with keys: headlines (list[str]), subheadline (str), "
        "benefit_bullets (list[str]), description_long (str), faq (list of objects "
        "with question/answer), urgency_text (str), cta_text (str)."
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
