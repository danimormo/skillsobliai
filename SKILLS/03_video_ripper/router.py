"""FastAPI router for the Video Ripper skill."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException

from core.errors import InvalidApiKeyError, InvalidParamsError, UpstreamError
from core.skill_interface import SkillContext, SkillResult

from .schemas import VideoRipperInput, VideoRipperOutput
from .service import VideoRipperSkill

logger = logging.getLogger(__name__)

router = APIRouter(tags=["video-ripper"])

_skill = VideoRipperSkill()


def _extract_user_id(authorization: str) -> str:
    """Extract user_id from Bearer token (placeholder implementation)."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    return token


@router.post("/run", response_model=SkillResult[VideoRipperOutput])
async def run_video_ripper(
    body: VideoRipperInput,
    authorization: str = Header(...),
) -> SkillResult[VideoRipperOutput]:
    """Download winning TikTok Shop video ads for a product."""
    user_id = _extract_user_id(authorization)
    ctx = SkillContext(user_id=user_id)

    try:
        result = await _skill.run(body, ctx)
    except InvalidParamsError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    except InvalidApiKeyError as exc:
        raise HTTPException(status_code=401, detail=exc.message) from exc
    except UpstreamError as exc:
        raise HTTPException(status_code=502, detail=exc.message) from exc

    return result
