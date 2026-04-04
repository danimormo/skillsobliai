import logging

from fastapi import APIRouter, Header, HTTPException

from core.errors import IntegrationNotConnectedError, MetaAPIError
from core.skill_interface import SkillContext, SkillResult

from SKILLS.campaign_validator.schemas import CampaignValidatorInput, CampaignValidatorOutput
from SKILLS.campaign_validator.service import CampaignValidatorSkill

logger = logging.getLogger(__name__)

router = APIRouter(tags=["campaign-validator"])

_skill = CampaignValidatorSkill()


def _extract_user_id(authorization: str) -> str:
    """Extract user_id from Bearer token (placeholder implementation)."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    return token


@router.post("/run", response_model=SkillResult[CampaignValidatorOutput])
async def run_campaign_validator(
    body: CampaignValidatorInput,
    authorization: str = Header(...),
) -> SkillResult[CampaignValidatorOutput]:
    """Validate campaign parameters before launch."""
    user_id = _extract_user_id(authorization)
    ctx = SkillContext(user_id=user_id)

    try:
        result = await _skill.run(body, ctx)
    except IntegrationNotConnectedError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    except MetaAPIError as exc:
        raise HTTPException(status_code=502, detail=exc.message) from exc

    return result
