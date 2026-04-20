import logging

from fastapi import APIRouter, Header, HTTPException

from core.errors import InvalidApiKeyError, InvalidParamsError, UpstreamError
from core.skill_interface import SkillContext, SkillResult

from .cost_tracker import CostCapExceeded
from .schemas import TrendAnalyzerInput, TrendAnalyzerOutput
from .service import TrendAnalyzerSkill

logger = logging.getLogger(__name__)

router = APIRouter(tags=["trend-analyzer"])

_skill = TrendAnalyzerSkill()


def _extract_user_id(authorization: str) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    return token


@router.post("/run", response_model=SkillResult[TrendAnalyzerOutput])
async def run_trend_analyzer(
    body: TrendAnalyzerInput,
    authorization: str = Header(...),
) -> SkillResult[TrendAnalyzerOutput]:
    """Run a full trend analysis pass on a text / URL / image input."""
    user_id = _extract_user_id(authorization)
    ctx = SkillContext(user_id=user_id)

    try:
        return await _skill.run(body, ctx)
    except InvalidParamsError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    except CostCapExceeded as exc:
        raise HTTPException(status_code=402, detail=exc.message) from exc
    except InvalidApiKeyError as exc:
        raise HTTPException(status_code=502, detail=exc.message) from exc
    except UpstreamError as exc:
        raise HTTPException(status_code=502, detail=exc.message) from exc
