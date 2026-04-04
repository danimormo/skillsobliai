import logging

from fastapi import APIRouter, Header, HTTPException

from core.errors import (
    InsufficientCreditsError,
    InvalidParamsError,
    VertexAIError,
)
from core.skill_interface import SkillContext, SkillResult

from .schemas import ImageCreatorInput, ImageCreatorOutput
from .service import ImageCreatorSkill

logger = logging.getLogger(__name__)

router = APIRouter(tags=["image-creator"])

_skill = ImageCreatorSkill()


def _extract_user_id(authorization: str) -> str:
    """Extract user_id from Bearer token (placeholder implementation)."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    return token


@router.post("/run", response_model=SkillResult[ImageCreatorOutput])
async def run_image_creator(
    body: ImageCreatorInput,
    authorization: str = Header(...),
) -> SkillResult[ImageCreatorOutput]:
    """Generate product images via Google Vertex AI Imagen 3."""
    user_id = _extract_user_id(authorization)
    ctx = SkillContext(user_id=user_id)

    try:
        result = await _skill.run(body, ctx)
    except InvalidParamsError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    except InsufficientCreditsError as exc:
        raise HTTPException(status_code=402, detail=exc.message) from exc
    except VertexAIError as exc:
        raise HTTPException(status_code=502, detail=exc.message) from exc

    return result
