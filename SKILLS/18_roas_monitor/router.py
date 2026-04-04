import logging

from fastapi import APIRouter, Header, HTTPException

from core.errors import InvalidApiKeyError, InvalidParamsError, UpstreamError
from core.skill_interface import SkillContext, SkillResult

from SKILLS.roas_monitor.schemas import ROASMonitorInput, ROASMonitorOutput
from SKILLS.roas_monitor.service import ROASMonitorSkill

logger = logging.getLogger(__name__)

router = APIRouter(tags=["roas-monitor"])

_skill = ROASMonitorSkill()


def _extract_user_id(authorization: str) -> str:
    """Extract user_id from Bearer token (placeholder implementation)."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    return token


@router.post("/run", response_model=SkillResult[ROASMonitorOutput])
async def run_roas_monitor(
    body: ROASMonitorInput,
    authorization: str = Header(...),
) -> SkillResult[ROASMonitorOutput]:
    """Run the ROAS monitor for all active campaigns."""
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
