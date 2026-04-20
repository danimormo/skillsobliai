"""Shared normalization prompt used for text / URL / image inputs."""

SYSTEM_PROMPT = (
    "You are a product research assistant for dropshippers. "
    "Given an input (image, URL content, or free text), extract a structured "
    "'product fingerprint' for downstream trend analysis. "
    "Return ONLY valid JSON matching the schema. No markdown, no explanations."
)

# Keep the schema section aligned with SKILLS.24_trend_analyzer.schemas.ProductFingerprint.
USER_PROMPT_TEMPLATE = """Extract:
- primary_keyword: the most searchable short phrase (2-4 words, English)
- secondary_keywords: 3-5 related keywords for broader search (English, lowercase)
- category: one of [fashion, home, beauty, electronics, fitness, pets, kids, kitchen, outdoor, other]
- estimated_retail_price_usd: number if visible or clearly inferrable, else null
- product_attributes: up to 5 key features (color, material, size, use case)

Return exactly this JSON shape:
{{
  "primary_keyword": "string",
  "secondary_keywords": ["string", ...],
  "category": "fashion|home|beauty|electronics|fitness|pets|kids|kitchen|outdoor|other",
  "estimated_retail_price_usd": number_or_null,
  "product_attributes": ["string", ...]
}}

Input:
{payload}
"""
