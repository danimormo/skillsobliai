import logging

from fastapi import APIRouter, Header, HTTPException

from core.errors import (
    InvalidApiKeyError,
    InvalidParamsError,
    RateLimitError,
    SkillBaseError,
    UpstreamError,
)
from core.skill_interface import SkillContext, SkillResult

from .schemas import TikTokAdsResearchInput, TikTokAdsResearchOutput
from .service import TikTokAdsResearcherSkill

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tiktok-ads-researcher"])

_skill = TikTokAdsResearcherSkill()


def _extract_user_id(authorization: str) -> str:
    """Extract user_id from Bearer token (placeholder implementation)."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    return token


@router.post("/run", response_model=SkillResult[TikTokAdsResearchOutput])
async def run_tiktok_ads_research(
    body: TikTokAdsResearchInput,
    authorization: str = Header(...),
) -> SkillResult[TikTokAdsResearchOutput]:
    """Execute the TikTok Ads Researcher skill."""
    user_id = _extract_user_id(authorization)
    ctx = SkillContext(user_id=user_id)

    if not _skill.validate(body):
        raise HTTPException(status_code=422, detail="Invalid input parameters")

    try:
        result = await _skill.run(body, ctx)
    except InvalidApiKeyError as exc:
        raise HTTPException(status_code=401, detail=exc.message) from exc
    except InvalidParamsError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    except RateLimitError as exc:
        raise HTTPException(status_code=429, detail=exc.message) from exc
    except UpstreamError as exc:
        raise HTTPException(status_code=502, detail=exc.message) from exc
    except SkillBaseError as exc:
        raise HTTPException(status_code=500, detail=exc.message) from exc

    return result
