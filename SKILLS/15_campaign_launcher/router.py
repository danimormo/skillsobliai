import logging

from fastapi import APIRouter, Header, HTTPException

from core.errors import IntegrationNotConnectedError, InvalidParamsError, ManusError, ManusTimeoutError, MetaAPIError
from core.skill_interface import SkillContext, SkillResult

from SKILLS.campaign_launcher.schemas import CampaignLauncherInput, CampaignLauncherOutput
from SKILLS.campaign_launcher.service import CampaignLauncherSkill

logger = logging.getLogger(__name__)

router = APIRouter(tags=["campaign-launcher"])

_skill = CampaignLauncherSkill()


def _extract_user_id(authorization: str) -> str:
    """Extract user_id from Bearer token (placeholder implementation)."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    return token


@router.post("/run", response_model=SkillResult[CampaignLauncherOutput])
async def run_campaign_launcher(
    body: CampaignLauncherInput,
    authorization: str = Header(...),
) -> SkillResult[CampaignLauncherOutput]:
    """Launch a Meta campaign via Manus AI."""
    user_id = _extract_user_id(authorization)
    ctx = SkillContext(user_id=user_id)

    try:
        result = await _skill.run(body, ctx)
    except InvalidParamsError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    except IntegrationNotConnectedError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    except (ManusError, ManusTimeoutError) as exc:
        raise HTTPException(status_code=502, detail=exc.message) from exc
    except MetaAPIError as exc:
        raise HTTPException(status_code=502, detail=exc.message) from exc

    return result
