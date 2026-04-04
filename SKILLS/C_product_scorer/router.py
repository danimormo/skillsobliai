import logging

from fastapi import APIRouter, Header, HTTPException

from core.errors import InvalidParamsError
from core.skill_interface import SkillContext, SkillResult

from .schemas import ProductScorerInput, ProductScorerOutput
from .service import ProductScorerSkill

logger = logging.getLogger(__name__)

router = APIRouter(tags=["product-scorer"])

_skill = ProductScorerSkill()


def _extract_user_id(authorization: str) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    return token


@router.post("/run", response_model=SkillResult[ProductScorerOutput])
async def run_skill(
    body: ProductScorerInput,
    authorization: str = Header(...),
) -> SkillResult[ProductScorerOutput]:
    """Score and rank products."""
    user_id = _extract_user_id(authorization)
    ctx = SkillContext(user_id=user_id)

    try:
        result = await _skill.run(body, ctx)
    except InvalidParamsError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc

    return result
