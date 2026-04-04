"""Tests for the google-researcher FastAPI router."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI

from core.skill_interface import SkillResult
from SKILLS.05_google_researcher.router import router
from SKILLS.05_google_researcher.schemas import GoogleResearchOutput

app = FastAPI()
app.include_router(router)


def _make_output() -> GoogleResearchOutput:
    return GoogleResearchOutput(
        keyword="test keyword",
        trend_direction="stable",
        trend_data=[],
        peak_months=[],
        reddit_posts=[],
        overall_sentiment="neutral",
        demand_score=42,
    )


@pytest.mark.asyncio
async def test_run_endpoint_success():
    """POST /google-researcher/run returns 200 with valid input."""
    output = _make_output()
    mock_result = SkillResult(success=True, data=output, cached=False, execution_ms=50)

    with patch(
        "SKILLS.05_google_researcher.router._skill.run",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/google-researcher/run",
                json={"keywords": ["test keyword"]},
                headers={"Authorization": "Bearer test-user-123"},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["keyword"] == "test keyword"
    assert body["data"]["demand_score"] == 42


@pytest.mark.asyncio
async def test_run_endpoint_missing_auth():
    """POST /google-researcher/run returns 422 when Authorization header is missing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/google-researcher/run",
            json={"keywords": ["test"]},
        )

    assert resp.status_code == 422
