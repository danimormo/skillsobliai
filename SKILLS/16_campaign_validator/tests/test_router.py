import importlib
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_router_mod = importlib.import_module("SKILLS.16_campaign_validator.router")
router = _router_mod.router

_schemas = importlib.import_module("SKILLS.16_campaign_validator.schemas")
CampaignValidatorOutput = _schemas.CampaignValidatorOutput
ValidationCheck = _schemas.ValidationCheck

from core.skill_interface import SkillResult

app = FastAPI()
app.include_router(router)
client = TestClient(app)

_VALID_BODY = {
    "ad_account_id": "act_456",
    "pixel_id": "px_123",
    "campaign_name": "Summer Sale IT",
    "daily_budget_usd": 20.0,
    "target_countries": ["IT"],
    "creative_image_urls": ["https://cdn.example.com/img1.jpg"],
    "ad_copy": "Shop the best deals!",
    "ad_headline": "Summer Sale",
    "destination_url": "https://test-store.com/summer",
    "product_price": 29.90,
    "product_cost": 8.0,
    "shipping_cost": 4.0,
}


def _make_skill_result() -> SkillResult[CampaignValidatorOutput]:
    return SkillResult(
        success=True,
        data=CampaignValidatorOutput(
            can_launch=True,
            checks=[
                ValidationCheck(name="budget_check", passed=True, message="OK", blocking=True),
            ],
            warnings=[],
            break_even_roas=0.40,
            summary="All blocking checks passed. Campaign is ready to launch.",
        ),
        cached=False,
        execution_ms=120,
    )


def test_run_success():
    """POST /run returns 200 with valid input."""
    with patch(
        "SKILLS.16_campaign_validator.router._skill.run",
        new_callable=AsyncMock,
        return_value=_make_skill_result(),
    ):
        response = client.post(
            "/run",
            json=_VALID_BODY,
            headers={"Authorization": "Bearer test-user-001"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["can_launch"] is True


def test_run_missing_auth():
    """POST /run without Authorization header returns 422."""
    response = client.post("/run", json=_VALID_BODY)
    assert response.status_code == 422
