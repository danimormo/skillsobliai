import json
import logging

import anthropic

from core.config import settings
from core.errors import UpstreamError

logger = logging.getLogger(__name__)

SKILL_NAME = "landing-builder"

SYSTEM_PROMPT = (
    "You are an expert landing page copywriter specializing in direct response "
    "advertorial copy for e-commerce. Generate landing page sections that convert. "
    "Respond ONLY with valid JSON. No markdown, no code fences, no explanations "
    "— just the JSON object."
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


async def generate_landing(
    product_title: str,
    product_description: str,
    price: float,
    original_price: float | None,
    target_audience: str,
    main_benefit: str,
    cta_destination_url: str,
    language: str,
) -> list[dict]:
    """Call Anthropic Claude to generate landing page copy.

    Returns a list of section dicts with keys: type, headline, body, cta_text.
    """
    user_prompt_parts = [
        f"Product: {product_title}",
        f"Description: {product_description}",
        f"Price: {price}",
        f"Target audience: {target_audience}",
        f"Main benefit: {main_benefit}",
        f"CTA destination: {cta_destination_url}",
        f"Language: {language}",
    ]
    if original_price:
        user_prompt_parts.append(f"Original price: {original_price}")
    user_prompt_parts.append(
        "\nReturn a JSON object with key 'sections': a list of objects, each with "
        "type (hero|benefits|testimonials|faq|cta), headline (str), body (str), "
        "cta_text (str or null)."
    )

    user_prompt = "\n".join(user_prompt_parts)

    try:
        content = await generate_with_claude(SYSTEM_PROMPT, user_prompt)
        parsed = json.loads(content)
        return parsed.get("sections", parsed) if isinstance(parsed, dict) else parsed
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
