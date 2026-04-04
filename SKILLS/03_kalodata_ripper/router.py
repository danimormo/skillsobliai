import logging

from fastapi import APIRouter, Header, HTTPException

from core.errors import SkillBaseError
from core.skill_interface import SkillContext, SkillResult

from SKILLS.03_kalodata_ripper.schemas import KalodataRipperInput, KalodataRipperOutput
from SKILLS.03_kalodata_ripper.service import KalodataRipperSkill

logger = logging.getLogger(__name__)

router = APIRouter(tags=["kalodata-ripper"])

_skill = KalodataRipperSkill()

_ERROR_STATUS_MAP = {
    "INVALID_API_KEY": 401,
    "INVALID_PARAMS": 422,
    "RATE_LIMIT": 429,
    "UPSTREAM_ERROR": 502,
}


def _extract_user_id(authorization: str) -> str:
    """Extract user_id from Bearer token (placeholder implementation)."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    return token


@router.post("/run", response_model=SkillResult[KalodataRipperOutput])
async def run_kalodata_ripper(
    body: KalodataRipperInput,
    authorization: str = Header(...),
) -> SkillResult[KalodataRipperOutput]:
    """Download top-performing TikTok Shop videos for a product."""
    user_id = _extract_user_id(authorization)
    ctx = SkillContext(user_id=user_id)
    try:
        result = await _skill.run(body, ctx)
    except SkillBaseError as exc:
        logger.warning("Skill error: %s", exc.message)
        raise HTTPException(
            status_code=_ERROR_STATUS_MAP.get(exc.code, 500),
            detail=exc.message,
        )
    return result
