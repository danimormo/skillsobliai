import logging

from fastapi import APIRouter, Header, HTTPException

from core.errors import (
    IntegrationNotConnectedError,
    InvalidParamsError,
    UpstreamError,
    RateLimitError,
)
from core.skill_interface import SkillContext, SkillResult

from SKILLS.product_importer.schemas import ProductImportInput, ProductImportOutput
from SKILLS.product_importer.service import ProductImporterSkill

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/product-importer", tags=["product-importer"])

_skill = ProductImporterSkill()


def _extract_user_id(authorization: str) -> str:
    """Extract user_id from Bearer token (placeholder implementation)."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    return token


@router.post("/run", response_model=SkillResult[ProductImportOutput])
async def run_product_import(
    body: ProductImportInput,
    authorization: str = Header(...),
) -> SkillResult[ProductImportOutput]:
    """Import a product into a Shopify store."""
    user_id = _extract_user_id(authorization)
    ctx = SkillContext(user_id=user_id)

    try:
        result = await _skill.run(body, ctx)
    except InvalidParamsError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    except IntegrationNotConnectedError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    except RateLimitError as exc:
        raise HTTPException(status_code=429, detail=exc.message) from exc
    except UpstreamError as exc:
        raise HTTPException(status_code=502, detail=exc.message) from exc

    return result
