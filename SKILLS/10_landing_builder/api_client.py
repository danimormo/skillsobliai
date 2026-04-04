import asyncio
import json
import logging

import httpx

from core.config import settings
from core.errors import InvalidApiKeyError, UpstreamError

logger = logging.getLogger(__name__)

SKILL_NAME = "landing-builder"
MAX_RETRIES = 3
BACKOFF_FACTORS = [1, 2, 4]

SYSTEM_PROMPT = (
    "You are an expert landing page copywriter for e-commerce. "
    "Generate landing page sections as a JSON array."
)


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
    """Call OpenRouter chat completions to generate landing page copy.

    Retries up to 3 times on 429 / 5xx with exponential backoff.
    Returns a list of section dicts with keys: type, headline, body, cta_text.
    """
    url = f"{settings.OPENROUTER_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

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

    payload = {
        "model": settings.OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "\n".join(user_prompt_parts)},
        ],
        "temperature": 0.7,
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
                parsed = json.loads(content)
                return parsed.get("sections", parsed) if isinstance(parsed, dict) else parsed

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
