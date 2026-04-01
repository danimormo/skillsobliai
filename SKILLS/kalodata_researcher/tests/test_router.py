"""Tests for kalodata-researcher FastAPI router."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI

from core.skill_interface import SkillResult

from SKILLS.kalodata_researcher.router import router
from SKILLS.kalodata_researcher.schemas import KalodataResearchOutput, KalodataProduct


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


app = _build_app()


@pytest.mark.asyncio
async def test_run_success():
    """POST /kalodata-researcher/run returns 200 with valid input and mocked skill."""
    output = KalodataResearchOutput(
        total_products=1,
        products=[
            KalodataProduct(
                product_id="p1",
                title="Test Product",
                category="Pets",
                price_range={"min": 5, "max": 10, "currency": "USD"},
                gmv_30d=50000.0,
                gmv_growth_pct=40.0,
                units_sold_30d=2000,
                shop_count=3,
                top_shop="Shop1",
                opportunity_score=26666.67,
                thumbnail_url=None,
            )
        ],
        region="US",
        days_range=30,
    )
    mock_result = SkillResult(success=True, data=output, cached=False, execution_ms=100)

    with patch(
        "SKILLS.kalodata_researcher.router._skill.run",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/kalodata-researcher/run",
                json={"keywords": ["dog toy"], "region": "US"},
                headers={"Authorization": "Bearer test-user-1"},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["total_products"] == 1
    assert body["data"]["products"][0]["product_id"] == "p1"


@pytest.mark.asyncio
async def test_run_validation_error():
    """POST /kalodata-researcher/run returns 422 when keywords are missing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/kalodata-researcher/run",
            json={"region": "US"},
            headers={"Authorization": "Bearer test-user-1"},
        )

    assert resp.status_code == 422
