import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.middleware import RequestIdMiddleware, ERROR_STATUS_MAP
from core.errors import SkillBaseError

from SKILLS.meta_ads_researcher.router import router as meta_ads_router
from SKILLS.kalodata_researcher.router import router as kalodata_router
from SKILLS.kalodata_ripper.router import router as kalodata_ripper_router
from SKILLS.tiktok_ads_researcher.router import router as tiktok_ads_router
from SKILLS.google_researcher.router import router as google_router
from SKILLS.content_researcher.router import router as content_router
from SKILLS.supplier_researcher.router import router as supplier_router
from SKILLS.product_importer.router import router as product_importer_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(title="SkillsObliai", version="1.0.0")

app.add_middleware(RequestIdMiddleware)


@app.exception_handler(SkillBaseError)
async def skill_error_handler(request: Request, exc: SkillBaseError):
    status_code = ERROR_STATUS_MAP.get(type(exc), 500)
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": exc.message,
            "code": exc.code,
            "skill": exc.skill,
        },
    )


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


app.include_router(meta_ads_router, prefix="/api/skills/meta-ads-researcher")
app.include_router(kalodata_router, prefix="/api/skills/kalodata-researcher")
app.include_router(kalodata_ripper_router, prefix="/api/skills/kalodata-ripper")
app.include_router(tiktok_ads_router, prefix="/api/skills/tiktok-ads-researcher")
app.include_router(google_router, prefix="/api/skills/google-researcher")
app.include_router(content_router, prefix="/api/skills/content-researcher")
app.include_router(supplier_router, prefix="/api/skills/supplier-researcher")
app.include_router(product_importer_router, prefix="/api/skills/product-importer")
