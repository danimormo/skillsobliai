import logging

from fastapi import APIRouter, Header, HTTPException

from core.errors import InvalidParamsError, UpstreamError
from core.skill_interface import SkillContext, SkillResult

from .schemas import PromptParserInput, PromptParserOutput
from .service import PromptParserSkill

logger = logging.getLogger(__name__)

router = APIRouter(tags=["prompt-parser"])

_skill = PromptParserSkill()


def _extract_user_id(authorization: str) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    return token


@router.post("/run", response_model=SkillResult[PromptParserOutput])
async def run_skill(
    body: PromptParserInput,
    authorization: str = Header(...),
) -> SkillResult[PromptParserOutput]:
    """Parse a free-text prompt into structured search parameters."""
    user_id = _extract_user_id(authorization)
    ctx = SkillContext(user_id=user_id)

    try:
        result = await _skill.run(body, ctx)
    except InvalidParamsError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    except UpstreamError as exc:
        raise HTTPException(status_code=502, detail=exc.message) from exc

    return result
