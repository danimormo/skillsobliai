import json
import logging

import anthropic

from core.config import settings

logger = logging.getLogger(__name__)

ACTIVE_COUNTRIES = [
    "US", "GB", "DE", "FR", "IT", "ID", "MY", "MX",
    "PH", "SG", "ES", "TH", "VN", "BR", "JP", "IE",
]

REGION_MAP = {
    "europe": ["GB", "DE", "FR", "IT", "ES", "IE"],
    "eu": ["GB", "DE", "FR", "IT", "ES", "IE"],
    "asia": ["ID", "MY", "PH", "SG", "TH", "VN", "JP"],
    "latam": ["MX", "BR"],
}

DEFAULT_PARAMS = {
    "sources": ["tiktok_shop"],
    "countries": ["US", "GB", "DE", "FR", "IT", "ES"],
    "n_results": 5,
    "search_signal": "winner",
    "categories": [],
    "gender": None,
    "price_max": None,
    "price_min": None,
    "keywords_by_country": {},
}


def build_system_prompt(keyword_pools: dict[str, list[str]]) -> str:
    """Build the system prompt that instructs Claude to parse user prompts."""
    pool_snippet = json.dumps(
        {k: v[:10] for k, v in keyword_pools.items()},
        ensure_ascii=False,
    )
    return f"""You are a search-parameter parser for an e-commerce product research tool.

Given a user prompt, extract structured JSON with these fields:
- sources: list of strings (valid: "tiktok_shop", "meta_ads"). Default ["tiktok_shop"].
- countries: list of ISO 2-letter country codes from this set: {json.dumps(ACTIVE_COUNTRIES)}.
  Region shortcuts: {json.dumps(REGION_MAP)}.
- n_results: integer 1-50, default 5.
- search_signal: one of "winner", "trending", "new", "rising". Default "winner".
- categories: list of product categories mentioned (empty if none).
- gender: "woman", "man", "unisex", or null.
- price_max: float or null.
- price_min: float or null.
- keywords_by_country: dict mapping each country code to a list of 6-8 search keywords
  in the LOCAL language of that country. Use these keyword pools as inspiration: {pool_snippet}

Return ONLY valid JSON. No markdown, no explanation."""


async def parse_prompt(prompt: str, system_prompt: str) -> tuple[dict, str]:
    """Call Claude Haiku to parse a user prompt into search parameters.

    Returns (parsed_dict, raw_response_text).
    """
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    response = await client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = response.content[0].text
    logger.debug("Claude raw response: %s", raw_text)

    parsed = json.loads(raw_text)
    return parsed, raw_text
