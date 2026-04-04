import base64
import logging

import anthropic
import httpx

from core.config import settings

logger = logging.getLogger(__name__)

VISION_SYSTEM_PROMPT = """You are a fashion product classifier. Analyze the image and return ONLY valid JSON:
{"is_fashion":bool,"confidence":float,"category":"tops|bottoms|dresses|outerwear|shoes|bags|accessories|activewear|swimwear|underwear|other_fashion|non_fashion","subcategory":str,"target_gender":"women|men|unisex|unknown","gender":"woman|man|unisex","price_tier":"budget|mid|premium|luxury|unknown","style_tags":[max 5],"reasoning":str,"eu_market_fit":bool}"""


async def download_image(image_url: str) -> tuple[str, str]:
    """Download an image and return (base64_data, media_type)."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(image_url)
        response.raise_for_status()

    content_type = response.headers.get("content-type", "image/jpeg")
    media_type = content_type.split(";")[0].strip()
    if media_type not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        media_type = "image/jpeg"

    b64 = base64.b64encode(response.content).decode("utf-8")
    return b64, media_type


async def classify_image(image_b64: str, media_type: str, title: str | None = None) -> dict:
    """Send an image to Claude Haiku Vision for classification.

    Returns the parsed JSON classification dict.
    """
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    user_content: list[dict] = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": image_b64,
            },
        },
    ]
    if title:
        user_content.append({"type": "text", "text": f"Product title: {title}"})
    else:
        user_content.append({"type": "text", "text": "Classify this product image."})

    response = await client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=512,
        system=VISION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    import json
    raw_text = response.content[0].text
    return json.loads(raw_text)
