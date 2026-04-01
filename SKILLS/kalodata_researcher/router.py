"""FastAPI router for the Kalodata Researcher skill."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException

from core.skill_interface import SkillContext, SkillResult
from core.errors import SkillBaseError

from .schemas import KalodataResearchInput, KalodataResearchOutput
from .service import KalodataResearcherSkill

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/kalodata-researcher", tags=["kalodata-researcher"])

_skill = KalodataResearcherSkill()


def _extract_user_id(authorization: str) -> str:
    """Extract user_id from a Bearer token (placeholder implementation)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Empty Bearer token")
    # Placeholder: treat the token as the user_id.
    # In production, decode/verify a JWT and extract the sub claim.
    return token


@router.post(
    "/run",
    response_model=SkillResult[KalodataResearchOutput],
    summary="Run Kalodata product research",
)
async def run_research(
    body: KalodataResearchInput,
    authorization: str = Header(default=""),
) -> SkillResult[KalodataResearchOutput]:
    user_id = _extract_user_id(authorization)

    if not _skill.validate(body):
        raise HTTPException(status_code=422, detail="Invalid input parameters")

    ctx = SkillContext(user_id=user_id)

    try:
        result = await _skill.run(body, ctx)
    except SkillBaseError as exc:
        logger.error("Skill error: %s (code=%s)", exc.message, exc.code)
        raise HTTPException(
            status_code=_status_for_skill_error(exc.code),
            detail=exc.message,
        )

    return result


def _status_for_skill_error(code: str) -> int:
    mapping: dict[str, int] = {
        "INVALID_API_KEY": 502,
        "INVALID_PARAMS": 422,
        "UPSTREAM_ERROR": 502,
        "RATE_LIMITED": 429,
    }
    return mapping.get(code, 500)
