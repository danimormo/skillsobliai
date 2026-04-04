"""Tests for TikTok Shop Researcher router."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI

from SKILLS.tiktok_shop_researcher.router import router
from SKILLS.tiktok_shop_researcher.schemas import TikTokShopOutput
from core.skill_interface import SkillResult


@pytest.fixture
def app():
    _app = FastAPI()
    _app.include_router(router)
    return _app


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ── Test 1: Successful research run ────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_success(app):
    """POST /run with valid auth returns 200."""
    mock_output = TikTokShopOutput(
        total_fetched=5,
        total_after_filter=3,
        products=[],
        countries_searched=["US"],
        countries_skipped=[],
        filter_tier_used=5,
    )
    mock_result = SkillResult(success=True, data=mock_output)

    with patch(
        "SKILLS.tiktok_shop_researcher.router._skill",
    ) as mock_skill:
        mock_skill.run = AsyncMock(return_value=mock_result)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/run",
                json={"countries": ["US"], "n_results": 5},
                headers={"Authorization": "Bearer test-user-123"},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["total_fetched"] == 5


# ── Test 2: Missing auth returns 422 ──────────────────────────────────────


@pytest.mark.asyncio
async def test_run_missing_auth(app):
    """POST /run without Authorization header returns 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/run",
            json={"countries": ["US"]},
        )

    assert resp.status_code == 422
