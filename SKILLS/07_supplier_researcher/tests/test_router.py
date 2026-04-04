"""Tests for the supplier-researcher router."""

import importlib

import pytest
from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI

from core.skill_interface import SkillResult

_router_mod = importlib.import_module("SKILLS.07_supplier_researcher.router")
router = _router_mod.router

_schemas = importlib.import_module("SKILLS.07_supplier_researcher.schemas")
SupplierResearchOutput = _schemas.SupplierResearchOutput
SupplierProduct = _schemas.SupplierProduct

app = FastAPI()
app.include_router(router)


def _sample_output() -> SupplierResearchOutput:
    product = SupplierProduct(
        source="aliexpress",
        product_id="ali_001",
        title="Test Earbuds",
        cost_usd=5.00,
        shipping_cost_usd=1.50,
        shipping_days_min=10,
        shipping_days_max=20,
        moq=1,
        supplier_rating=4.8,
        image_urls=["https://img.example.com/1.jpg"],
        product_url="https://aliexpress.com/item/ali_001",
        margin_at_3x=0.78,
        in_stock=True,
    )
    return SupplierResearchOutput(
        total_found=1,
        products=[product],
        best_price=product,
        best_margin=product,
        fastest_shipping=product,
    )


@pytest.mark.asyncio
@patch("SKILLS.07_supplier_researcher.router._skill")
async def test_run_endpoint_success(mock_skill):
    """Test POST /supplier-researcher/run returns 200 on success."""
    mock_skill.run = AsyncMock(
        return_value=SkillResult(
            success=True,
            data=_sample_output(),
            cached=False,
            execution_ms=150,
        )
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/supplier-researcher/run",
            json={
                "product_name": "wireless earbuds",
                "target_price_usd": 29.99,
                "sources": ["aliexpress"],
                "limit_per_source": 5,
            },
            headers={"Authorization": "Bearer test_user_123"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["total_found"] == 1
    assert len(body["data"]["products"]) == 1


@pytest.mark.asyncio
async def test_run_endpoint_missing_auth():
    """Test POST /supplier-researcher/run returns 422 when Authorization header is missing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/supplier-researcher/run",
            json={"product_name": "wireless earbuds"},
        )

    assert response.status_code == 422
