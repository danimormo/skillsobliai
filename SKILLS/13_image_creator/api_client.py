import logging

import httpx

from core.config import settings
from core.errors import FALError

logger = logging.getLogger(__name__)

VARIANT_PROMPTS = {
    "product_shot": "professional product photography, white background, studio lighting, sharp focus, 8k",
    "lifestyle": "lifestyle photography, natural setting, person using product, natural lighting",
    "close_up": "macro photography, extreme close-up, product detail, texture, 8k",
    "before_after": "split composition, before and after comparison, transformation visual",
    "ugc_style": "candid smartphone photo, authentic feel, user generated content, slightly imperfect",
}

TIMEOUT = 60.0


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Key {settings.FAL_API_KEY}",
        "Content-Type": "application/json",
    }


async def text_to_image(
    prompt: str,
    image_size: str = "square_hd",
    num_images: int = 1,
) -> dict:
    """Generate images from a text prompt via FAL.ai Flux.2 Pro."""
    url = f"{settings.FAL_BASE_URL}/fal-ai/flux-pro"
    payload = {
        "prompt": prompt,
        "image_size": image_size,
        "num_images": num_images,
    }

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            resp = await client.post(url, headers=_headers(), json=payload)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("FAL text-to-image HTTP %s: %s", exc.response.status_code, exc.response.text)
            raise FALError(
                message=f"FAL API error: {exc.response.status_code}",
                skill="image-creator",
                code="FAL_HTTP_ERROR",
            ) from exc
        except httpx.TimeoutException as exc:
            logger.error("FAL text-to-image timeout")
            raise FALError(
                message="FAL API request timed out",
                skill="image-creator",
                code="FAL_TIMEOUT",
            ) from exc


async def image_to_image(
    prompt: str,
    image_url: str,
    image_size: str = "square_hd",
    num_images: int = 1,
) -> dict:
    """Generate images from a source image + prompt via FAL.ai Flux.2 Pro."""
    url = f"{settings.FAL_BASE_URL}/fal-ai/flux-pro/image-to-image"
    payload = {
        "prompt": prompt,
        "image_url": image_url,
        "image_size": image_size,
        "num_images": num_images,
    }

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            resp = await client.post(url, headers=_headers(), json=payload)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("FAL image-to-image HTTP %s: %s", exc.response.status_code, exc.response.text)
            raise FALError(
                message=f"FAL API error: {exc.response.status_code}",
                skill="image-creator",
                code="FAL_HTTP_ERROR",
            ) from exc
        except httpx.TimeoutException as exc:
            logger.error("FAL image-to-image timeout")
            raise FALError(
                message="FAL API request timed out",
                skill="image-creator",
                code="FAL_TIMEOUT",
            ) from exc
