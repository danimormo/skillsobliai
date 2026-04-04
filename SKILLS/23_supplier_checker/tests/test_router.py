from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from SKILLS.supplier_checker.router import router
from SKILLS.supplier_checker.schemas import SupplierCheckerOutput
from core.skill_interface import SkillResult

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def _make_skill_result() -> SkillResult[SupplierCheckerOutput]:
    return SkillResult(
        success=True,
        data=SupplierCheckerOutput(
            product_title="LED posture corrector",
            sale_price=39.99,
            best_supplier_cost=8.50,
            best_supplier_source="aliexpress",
            net_margin_pct=0.37,
            net_margin_usd=14.83,
            is_viable=True,
            flag="green",
            breakdown={"supplier": 8.50, "shipping": 4.0, "ads_per_order": 10.0,
                        "shopify_fee": 1.46, "refund_buffer": 1.20},
            recommendation="Strong margin of 37.0%.",
            alternative_suppliers=[],
        ),
        cached=False,
        execution_ms=850,
    )


def test_run_success():
    """POST /supplier-checker/run returns 200 with valid input."""
    with patch(
        "SKILLS.supplier_checker.router._skill.run",
        new_callable=AsyncMock,
        return_value=_make_skill_result(),
    ):
        response = client.post(
            "/run",
            json={
                "product_title": "LED posture corrector",
                "sale_price": 39.99,
                "supplier_cost": 8.50,
            },
            headers={"Authorization": "Bearer test-user-001"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["is_viable"] is True
    assert body["data"]["flag"] == "green"


def test_run_missing_auth():
    """POST without Authorization header returns 422 (missing required header)."""
    response = client.post(
        "/run",
        json={
            "product_title": "LED posture corrector",
            "sale_price": 39.99,
        },
    )
    assert response.status_code == 422
