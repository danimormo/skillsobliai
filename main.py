import importlib
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.middleware import RequestIdMiddleware
from core.errors import SkillBaseError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(title="SkillsObliai", version="2.0.0")

app.add_middleware(RequestIdMiddleware)

# ── Error handling ──────────────────────────────────────────────────────


ERROR_STATUS_MAP: dict[type, int] = {}


def _build_error_map() -> None:
    from core.errors import (
        TokenExpiredError, TokenMissingError, InvalidApiKeyError,
        RateLimitError, InvalidParamsError, UpstreamError,
        InsufficientCreditsError, IntegrationNotConnectedError,
        FALError, FALTimeoutError, ManusError, ManusTimeoutError,
        ShopifyError, MetaAPIError, StripeWebhookError,
    )
    ERROR_STATUS_MAP.update({
        TokenExpiredError: 401,
        TokenMissingError: 401,
        InvalidApiKeyError: 401,
        RateLimitError: 429,
        InvalidParamsError: 422,
        UpstreamError: 502,
        InsufficientCreditsError: 402,
        IntegrationNotConnectedError: 403,
        FALError: 502,
        FALTimeoutError: 504,
        ManusError: 502,
        ManusTimeoutError: 504,
        ShopifyError: 502,
        MetaAPIError: 502,
        StripeWebhookError: 400,
    })


_build_error_map()


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


# ── Health check ────────────────────────────────────────────────────────


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


# ── Helper to import from numeric-prefixed directories ──────────────────


def _import_router(module_path: str):
    """Import router from a skill module (supports numeric-prefixed dirs)."""
    mod = importlib.import_module(module_path)
    return mod.router


# ── Register all skill routers ──────────────────────────────────────────

_SKILL_ROUTES = [
    ("SKILLS.A_prompt_parser.router", "/api/skills/prompt-parser"),
    ("SKILLS.B_vision_classifier.router", "/api/skills/vision-classifier"),
    ("SKILLS.C_product_scorer.router", "/api/skills/product-scorer"),
    ("SKILLS.01_meta_ads_researcher.router", "/api/skills/meta-ads-researcher"),
    ("SKILLS.02_tiktok_shop_researcher.router", "/api/skills/tiktok-shop-researcher"),
    ("SKILLS.03_kalodata_ripper.router", "/api/skills/kalodata-ripper"),
    ("SKILLS.04_tiktok_ads_researcher.router", "/api/skills/tiktok-ads-researcher"),
    ("SKILLS.05_google_researcher.router", "/api/skills/google-researcher"),
    ("SKILLS.06_content_researcher.router", "/api/skills/content-researcher"),
    ("SKILLS.07_supplier_researcher.router", "/api/skills/supplier-researcher"),
    ("SKILLS.08_product_importer.router", "/api/skills/product-importer"),
    ("SKILLS.09_pdp_builder.router", "/api/skills/pdp-builder"),
    ("SKILLS.10_landing_builder.router", "/api/skills/landing-builder"),
    ("SKILLS.11_theme_configurator.router", "/api/skills/theme-configurator"),
    ("SKILLS.12_creative_ideator.router", "/api/skills/creative-ideator"),
    ("SKILLS.13_image_creator.router", "/api/skills/image-creator"),
    ("SKILLS.14_video_generator.router", "/api/skills/video-generator"),
    ("SKILLS.15_campaign_launcher.router", "/api/skills/campaign-launcher"),
    ("SKILLS.16_campaign_validator.router", "/api/skills/campaign-validator"),
    ("SKILLS.18_roas_monitor.router", "/api/skills/roas-monitor"),
    ("SKILLS.20_scale_kill_engine.router", "/api/skills/scale-kill-engine"),
    ("SKILLS.21_smart_scorer.router", "/api/skills/smart-scorer"),
    ("SKILLS.22_saturation_detector.router", "/api/skills/saturation-detector"),
    ("SKILLS.23_supplier_checker.router", "/api/skills/supplier-checker"),
    ("SKILLS.25_stripe_billing.router", "/api/billing"),
]

for module_path, prefix in _SKILL_ROUTES:
    app.include_router(_import_router(module_path), prefix=prefix)
