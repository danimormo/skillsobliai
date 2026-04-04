import logging

from fastapi import APIRouter, Header, HTTPException

from core.errors import InvalidApiKeyError, InvalidParamsError, UpstreamError
from core.skill_interface import SkillContext, SkillResult

from SKILLS.scale_kill_engine.schemas import ScaleKillInput, ScaleKillOutput
from SKILLS.scale_kill_engine.service import ScaleKillEngineSkill

logger = logging.getLogger(__name__)

router = APIRouter(tags=["scale-kill-engine"])

_skill = ScaleKillEngineSkill()


def _extract_user_id(authorization: str) -> str:
    """Extract user_id from Bearer token (placeholder implementation)."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    return token


@router.post("/run", response_model=SkillResult[ScaleKillOutput])
async def run_scale_kill_engine(
    body: ScaleKillInput,
    authorization: str = Header(...),
) -> SkillResult[ScaleKillOutput]:
    """Evaluate and execute ROAS-based scale/kill/duplicate rules."""
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
