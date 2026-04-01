import logging

from fastapi import APIRouter, HTTPException

from core.errors import SkillBaseError
from core.skill_interface import SkillContext

from SKILLS.kalodata_ripper.schemas import KalodataRipperInput, KalodataRipperOutput
from SKILLS.kalodata_ripper.service import KalodataRipperSkill

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kalodata-ripper", tags=["kalodata-ripper"])

_skill = KalodataRipperSkill()


@router.post("/run")
async def run_kalodata_ripper(
    input: KalodataRipperInput,
    user_id: str = "anonymous",
) -> dict:
    """Download top-performing TikTok Shop videos for a product."""
    ctx = SkillContext(user_id=user_id)
    try:
        result = await _skill.run(input, ctx)
        return result.model_dump()
    except SkillBaseError as exc:
        logger.warning("Skill error: %s", exc.message)
        status_map = {
            "INVALID_API_KEY": 401,
            "INVALID_PARAMS": 422,
            "RATE_LIMIT": 429,
            "UPSTREAM_ERROR": 502,
        }
        raise HTTPException(
            status_code=status_map.get(exc.code, 500),
            detail=exc.message,
        )
