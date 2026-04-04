import logging

from fastapi import APIRouter, Header, HTTPException

from core.errors import InvalidApiKeyError, InvalidParamsError, UpstreamError
from core.skill_interface import SkillContext, SkillResult

from SKILLS.supplier_checker.schemas import SupplierCheckerInput, SupplierCheckerOutput
from SKILLS.supplier_checker.service import SupplierCheckerSkill

logger = logging.getLogger(__name__)

router = APIRouter(tags=["supplier-checker"])

_skill = SupplierCheckerSkill()


def _extract_user_id(authorization: str) -> str:
    """Extract user_id from Bearer token (placeholder implementation)."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    return token


@router.post("/run", response_model=SkillResult[SupplierCheckerOutput])
async def run_supplier_checker(
    body: SupplierCheckerInput,
    authorization: str = Header(...),
) -> SkillResult[SupplierCheckerOutput]:
    """Run a supplier viability check with margin calculation."""
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
