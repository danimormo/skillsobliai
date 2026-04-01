from fastapi import APIRouter, HTTPException

from core.errors import (
    InvalidApiKeyError,
    InvalidParamsError,
    SkillBaseError,
    UpstreamError,
)
from core.skill_interface import SkillContext, SkillResult

from .schemas import TikTokAdsResearchInput, TikTokAdsResearchOutput
from .service import TikTokAdsResearcherSkill

router = APIRouter(prefix="/tiktok-ads-researcher", tags=["tiktok-ads-researcher"])

_skill = TikTokAdsResearcherSkill()


class RunRequest(TikTokAdsResearchInput):
    """Request body extends the input schema with context fields."""

    user_id: str


@router.post("/run", response_model=SkillResult[TikTokAdsResearchOutput])
async def run(body: RunRequest) -> SkillResult[TikTokAdsResearchOutput]:
    """Execute the TikTok Ads Researcher skill."""
    ctx = SkillContext(user_id=body.user_id)
    input_data = TikTokAdsResearchInput(
        keywords=body.keywords,
        regions=body.regions,
        industry=body.industry,
        days_range=body.days_range,
        limit=body.limit,
    )

    if not _skill.validate(input_data):
        raise HTTPException(status_code=422, detail="Invalid input parameters")

    try:
        result = await _skill.run(input_data, ctx)
    except InvalidApiKeyError as exc:
        raise HTTPException(status_code=401, detail=exc.message)
    except InvalidParamsError as exc:
        raise HTTPException(status_code=422, detail=exc.message)
    except UpstreamError as exc:
        raise HTTPException(status_code=502, detail=exc.message)
    except SkillBaseError as exc:
        raise HTTPException(status_code=500, detail=exc.message)

    return result
