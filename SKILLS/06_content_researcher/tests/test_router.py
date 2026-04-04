"""Tests for the content-researcher router."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.skill_interface import SkillResult
from SKILLS.06_content_researcher.router import router
from SKILLS.06_content_researcher.schemas import ContentResearchOutput

app = FastAPI()
app.include_router(router)

client = TestClient(app)


_MOCK_OUTPUT = ContentResearchOutput(
    total_items=2,
    items=[],
    top_formats=["ugc", "review"],
    top_angles=["lifestyle", "social_proof"],
    avg_engagement_rate=0.045,
    content_insights="Analyzed 2 items.",
)

_MOCK_RESULT = SkillResult(
    success=True,
    data=_MOCK_OUTPUT,
    cached=False,
    execution_ms=150,
)


def test_run_endpoint_success():
    """POST /content-researcher/run returns 200 with valid input."""
    with patch(
        "SKILLS.06_content_researcher.router._skill.run",
        new_callable=AsyncMock,
        return_value=_MOCK_RESULT,
    ):
        response = client.post(
            "/content-researcher/run",
            json={
                "keywords": ["protein powder"],
                "platforms": ["tiktok"],
                "region": "US",
                "limit_per_platform": 10,
            },
            headers={"Authorization": "Bearer test_user_123"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["total_items"] == 2
    assert body["data"]["top_formats"] == ["ugc", "review"]


def test_run_endpoint_missing_auth():
    """POST /content-researcher/run returns 422 when Authorization header is absent."""
    response = client.post(
        "/content-researcher/run",
        json={"keywords": ["test"]},
    )
    assert response.status_code == 422
