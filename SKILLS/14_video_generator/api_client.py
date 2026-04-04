import asyncio
import time

import vertexai
from vertexai.preview.vision_models import VideoGenerationModel

from core.config import settings
from core.errors import VertexAIError, VertexAITimeoutError


def submit_video_generation(
    prompt: str,
    image_bytes: bytes | None = None,
    aspect_ratio: str = "9:16",
):
    """Submit a Veo 2 video generation job. Returns a long-running operation."""
    try:
        vertexai.init(
            project=settings.GOOGLE_CLOUD_PROJECT,
            location=settings.GOOGLE_CLOUD_LOCATION,
        )
        model = VideoGenerationModel.from_pretrained(settings.VERTEX_VIDEO_MODEL)
        if image_bytes:
            operation = model.generate_video(
                prompt=prompt,
                image=image_bytes,
                duration_seconds=5,
                aspect_ratio=aspect_ratio,
            )
        else:
            operation = model.generate_video(
                prompt=prompt,
                duration_seconds=5,
                aspect_ratio=aspect_ratio,
            )
        return operation
    except Exception as e:
        raise VertexAIError(
            f"Veo 2 submission failed: {e}",
            skill="video-generator",
            code="VERTEX_VIDEO_ERROR",
        ) from e


async def poll_video_operation(
    operation,
    timeout_seconds: int = 300,
) -> bytes:
    """Poll Veo 2 operation every 10s until done. Timeout 300s."""
    start = time.monotonic()
    while True:
        if operation.done():
            result = operation.result()
            return result.videos[0]._video_bytes
        elapsed = time.monotonic() - start
        if elapsed > timeout_seconds:
            raise VertexAITimeoutError(
                f"Veo 2 timeout after {timeout_seconds}s",
                skill="video-generator",
                code="VERTEX_VIDEO_TIMEOUT",
            )
        await asyncio.sleep(10)
