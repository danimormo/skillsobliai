from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.skill_interface import SkillResult
from SKILLS.04_tiktok_ads_researcher.router import router
from SKILLS.04_tiktok_ads_researcher.schemas import TikTokAdsResearchOutput

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def _build_payload(**overrides) -> dict:
    base = {
        "user_id": "user-1",
        "keywords": ["skincare"],
        "regions": ["US"],
        "industry": "ecommerce",
        "days_range": 30,
        "limit": 50,
    }
    base.update(overrides)
    return base


# ------------------------------------------------------------------
# Successful run
# ------------------------------------------------------------------


def test_run_success() -> None:
    output = TikTokAdsResearchOutput(
        total_ads=0,
        ads=[],
        keywords=["skincare"],
        regions=["US"],
    )
    skill_result = SkillResult(
        success=True,
        data=output,
        cached=False,
        execution_ms=100,
    )

    with patch(
        "SKILLS.04_tiktok_ads_researcher.router._skill.run",
        new_callable=AsyncMock,
        return_value=skill_result,
    ):
        resp = client.post("/tiktok-ads-researcher/run", json=_build_payload())

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["keywords"] == ["skincare"]


# ------------------------------------------------------------------
# Validation error (missing required field)
# ------------------------------------------------------------------


def test_run_validation_error() -> None:
    payload = _build_payload()
    del payload["keywords"]  # keywords is required

    resp = client.post("/tiktok-ads-researcher/run", json=payload)
    assert resp.status_code == 422
