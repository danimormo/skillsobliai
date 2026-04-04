import logging

from fastapi import APIRouter, Header, HTTPException

from core.errors import (
    IntegrationNotConnectedError,
    InvalidParamsError,
    ShopifyError,
    UpstreamError,
)
from core.skill_interface import SkillContext, SkillResult

from SKILLS.theme_configurator.schemas import (
    ThemeConfiguratorInput,
    ThemeConfiguratorOutput,
)
from SKILLS.theme_configurator.service import ThemeConfiguratorSkill

logger = logging.getLogger(__name__)

router = APIRouter(tags=["theme-configurator"])

_skill = ThemeConfiguratorSkill()


def _extract_user_id(authorization: str) -> str:
    """Extract user_id from Bearer token (placeholder implementation)."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    return token


@router.post("/run", response_model=SkillResult[ThemeConfiguratorOutput])
async def run_theme_configurator(
    body: ThemeConfiguratorInput,
    authorization: str = Header(...),
) -> SkillResult[ThemeConfiguratorOutput]:
    """Configure Shopify theme settings."""
    user_id = _extract_user_id(authorization)
    ctx = SkillContext(user_id=user_id)

    try:
        result = await _skill.run(body, ctx)
    except InvalidParamsError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    except IntegrationNotConnectedError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    except ShopifyError as exc:
        raise HTTPException(status_code=502, detail=exc.message) from exc
    except UpstreamError as exc:
        raise HTTPException(status_code=502, detail=exc.message) from exc

    return result
