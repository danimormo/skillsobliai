from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from SKILLS.campaign_launcher.router import router
from SKILLS.campaign_launcher.schemas import CampaignLauncherOutput
from core.skill_interface import SkillResult

app = FastAPI()
app.include_router(router)
client = TestClient(app)

_VALID_BODY = {
    "shop_domain": "test-store.myshopify.com",
    "campaign_name": "Summer Sale IT",
    "daily_budget_usd": 20.0,
    "target_countries": ["IT"],
    "pixel_id": "px_123",
    "ad_account_id": "act_456",
    "creative_image_urls": ["https://cdn.example.com/img1.jpg"],
    "ad_copy": "Shop the best deals!",
    "ad_headline": "Summer Sale",
    "destination_url": "https://test-store.com/summer",
}


def _make_skill_result() -> SkillResult[CampaignLauncherOutput]:
    return SkillResult(
        success=True,
        data=CampaignLauncherOutput(
            campaign_db_id="db_001",
            meta_campaign_id="camp_111",
            meta_adset_id="adset_222",
            meta_ad_id="ad_333",
            campaign_name="Summer Sale IT",
            status="ACTIVE",
            daily_budget_usd=20.0,
            manus_task_id="task_001",
            launched_at="2026-04-04T12:00:00+00:00",
        ),
        cached=False,
        execution_ms=5000,
    )


def test_run_success():
    """POST /run returns 200 with valid input."""
    with patch(
        "SKILLS.campaign_launcher.router._skill.run",
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
    assert body["data"]["meta_campaign_id"] == "camp_111"


def test_run_missing_auth():
    """POST /run without Authorization header returns 422."""
    response = client.post("/run", json=_VALID_BODY)
    assert response.status_code == 422
