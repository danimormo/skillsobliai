"""Image → ProductFingerprint via Claude Haiku vision."""

from __future__ import annotations

import base64
import logging
import mimetypes
from pathlib import Path

import httpx

from core.errors import InvalidParamsError, UpstreamError

from ..cost_tracker import CostTracker
from ..llm import call_haiku_json
from ..schemas import ProductFingerprint
from ._prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from .text import _to_fingerprint

logger = logging.getLogger(__name__)

SKILL_NAME = "trend-analyzer"
REQUEST_TIMEOUT_S = 15.0
MAX_IMAGE_BYTES = 5 * 1024 * 1024

SUPPORTED_MEDIA_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


async def normalize_image(
    *,
    image_url: str | None,
    image_b64: str | None,
    cost: CostTracker,
) -> ProductFingerprint:
    if bool(image_url) == bool(image_b64):
        raise InvalidParamsError(
            message="Provide exactly one of image_url or image_b64.",
            skill=SKILL_NAME,
            code="INVALID_PARAMS",
        )

    if image_url:
        b64_data, media_type = await _download_and_encode(image_url)
        raw_input = image_url
    else:
        b64_data = _strip_data_url_prefix(image_b64 or "")
        media_type = _guess_media_type_from_b64(b64_data)
        raw_input = "<base64 image>"

    payload = await call_haiku_json(
        system=SYSTEM_PROMPT,
        user=USER_PROMPT_TEMPLATE.format(
            payload="product photo — describe the visible item, color, material, and intended use."
        ),
        cost=cost,
        operation="normalize_image",
        image_b64=b64_data,
        image_media_type=media_type,
        max_tokens=500,
    )

    return _to_fingerprint(payload, source_kind="image", raw_input=raw_input)


async def _download_and_encode(image_url: str) -> tuple[str, str]:
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S, follow_redirects=True) as client:
            resp = await client.get(image_url)
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        raise UpstreamError(
            message=f"Failed to download image: {exc}",
            skill=SKILL_NAME,
            code="CONNECTION",
        ) from exc

    if resp.status_code >= 400:
        raise UpstreamError(
            message=f"Image URL returned HTTP {resp.status_code}",
            skill=SKILL_NAME,
            code="UPSTREAM_ERROR",
        )

    data = resp.content
    if len(data) > MAX_IMAGE_BYTES:
        raise InvalidParamsError(
            message=f"Image exceeds {MAX_IMAGE_BYTES} bytes.",
            skill=SKILL_NAME,
            code="IMAGE_TOO_LARGE",
        )

    media_type = (
        resp.headers.get("content-type", "").split(";")[0].strip()
        or mimetypes.guess_type(Path(image_url).name)[0]
        or "image/jpeg"
    )
    if media_type not in SUPPORTED_MEDIA_TYPES:
        media_type = "image/jpeg"

    return base64.b64encode(data).decode("ascii"), media_type


def _strip_data_url_prefix(b64: str) -> str:
    if b64.startswith("data:"):
        _, _, rest = b64.partition(",")
        return rest
    return b64


def _guess_media_type_from_b64(b64: str) -> str:
    try:
        head = base64.b64decode(b64[:32], validate=False)
    except Exception:
        return "image/jpeg"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG"):
        return "image/png"
    if head[0:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head.startswith(b"GIF8"):
        return "image/gif"
    return "image/jpeg"
