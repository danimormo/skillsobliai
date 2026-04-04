from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI

from SKILLS.08_product_importer.router import router
from SKILLS.08_product_importer.schemas import ProductImportOutput
from core.skill_interface import SkillResult

app = FastAPI()
app.include_router(router)


def _sample_body() -> dict:
    return {
        "shop_domain": "test-store.myshopify.com",
        "title": "Test Product",
        "description_html": "<p>description</p>",
        "image_urls": ["https://cdn.example.com/img.jpg"],
        "cost_usd": 5.0,
        "markup_multiplier": 3.0,
    }


def _success_result() -> SkillResult[ProductImportOutput]:
    return SkillResult(
        success=True,
        data=ProductImportOutput(
            job_id="job-001",
            shopify_product_id="111",
            shopify_product_url="https://test-store.myshopify.com/admin/products/111",
            shopify_storefront_url="https://test-store.myshopify.com/products/test-product",
            title="Test Product",
            price=15.0,
            variants_count=1,
            images_uploaded=1,
            status="completed",
        ),
        cached=False,
        execution_ms=200,
    )


@pytest.mark.asyncio
async def test_run_endpoint_success():
    """POST /product-importer/run returns 200 with valid payload."""
    with patch(
        "SKILLS.08_product_importer.router._skill",
    ) as mock_skill:
        mock_skill.run = AsyncMock(return_value=_success_result())

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/product-importer/run",
                json=_sample_body(),
                headers={"Authorization": "Bearer test-user-001"},
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["shopify_product_id"] == "111"
    assert data["data"]["status"] == "completed"


@pytest.mark.asyncio
async def test_run_endpoint_missing_auth():
    """POST /product-importer/run without Authorization returns 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/product-importer/run",
            json=_sample_body(),
        )

    assert resp.status_code == 422
