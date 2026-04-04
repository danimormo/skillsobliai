import asyncio
import logging

import httpx

from core.config import settings
from core.errors import FALError, FALTimeoutError

logger = logging.getLogger(__name__)

SUBMIT_URL = f"{settings.FAL_BASE_URL}/fal-ai/kling-video/v2/master/image-to-video"
POLL_INTERVAL = 5  # seconds
POLL_TIMEOUT = 120  # seconds


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Key {settings.FAL_API_KEY}",
        "Content-Type": "application/json",
    }


async def submit_video(
    prompt: str,
    image_url: str,
    duration: str = "5",
    aspect_ratio: str = "9:16",
) -> dict:
    """Submit a video generation request to FAL.ai Kling 2.6."""
    payload = {
        "prompt": prompt,
        "image_url": image_url,
        "duration": duration,
        "aspect_ratio": aspect_ratio,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(SUBMIT_URL, headers=_headers(), json=payload)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("FAL submit HTTP %s: %s", exc.response.status_code, exc.response.text)
            raise FALError(
                message=f"FAL API error: {exc.response.status_code}",
                skill="video-generator",
                code="FAL_HTTP_ERROR",
            ) from exc
        except httpx.TimeoutException as exc:
            logger.error("FAL submit timeout")
            raise FALError(
                message="FAL API request timed out",
                skill="video-generator",
                code="FAL_TIMEOUT",
            ) from exc


async def poll_video(request_id: str) -> dict:
    """Poll for video generation completion. Returns result on success."""
    status_url = f"{SUBMIT_URL}/requests/{request_id}/status"
    elapsed = 0.0

    async with httpx.AsyncClient(timeout=15.0) as client:
        while elapsed < POLL_TIMEOUT:
            try:
                resp = await client.get(status_url, headers=_headers())
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPStatusError as exc:
                logger.error("FAL poll HTTP %s: %s", exc.response.status_code, exc.response.text)
                raise FALError(
                    message=f"FAL poll error: {exc.response.status_code}",
                    skill="video-generator",
                    code="FAL_POLL_ERROR",
                ) from exc
            except httpx.TimeoutException as exc:
                logger.warning("FAL poll request timed out, retrying")
                await asyncio.sleep(POLL_INTERVAL)
                elapsed += POLL_INTERVAL
                continue

            status = data.get("status")
            if status == "COMPLETED":
                return data
            if status in ("FAILED", "CANCELLED"):
                raise FALError(
                    message=f"Video generation {status.lower()}: {data.get('error', 'unknown')}",
                    skill="video-generator",
                    code="FAL_GENERATION_FAILED",
                )

            await asyncio.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL

    raise FALTimeoutError(
        message=f"Video generation timed out after {POLL_TIMEOUT}s (request_id={request_id})",
        skill="video-generator",
        code="FAL_TIMEOUT",
    )
