import logging

from fastapi import APIRouter, Header, HTTPException

from core.errors import InvalidApiKeyError, InvalidParamsError, UpstreamError
from core.skill_interface import SkillContext, SkillResult

from SKILLS.saturation_detector.schemas import SaturationDetectorInput, SaturationDetectorOutput
from SKILLS.saturation_detector.service import SaturationDetectorSkill

logger = logging.getLogger(__name__)

router = APIRouter(tags=["saturation-detector"])

_skill = SaturationDetectorSkill()


def _extract_user_id(authorization: str) -> str:
    """Extract user_id from Bearer token (placeholder implementation)."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    return token


@router.post("/run", response_model=SkillResult[SaturationDetectorOutput])
async def run_saturation_detector(
    body: SaturationDetectorInput,
    authorization: str = Header(...),
) -> SkillResult[SaturationDetectorOutput]:
    """Run a product saturation check across Shopify stores."""
    user_id = _extract_user_id(authorization)
    ctx = SkillContext(user_id=user_id)

    try:
        result = await _skill.run(body, ctx)
    except InvalidParamsError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    except InvalidApiKeyError as exc:
        raise HTTPException(status_code=502, detail=exc.message) from exc
    except UpstreamError as exc:
        raise HTTPException(status_code=502, detail=exc.message) from exc

    return result
