from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from SKILLS.C_product_scorer.router import router
from SKILLS.C_product_scorer.schemas import ProductScorerOutput, ScoredProduct
from core.skill_interface import SkillResult

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def _make_skill_result() -> SkillResult[ProductScorerOutput]:
    return SkillResult(
        success=True,
        data=ProductScorerOutput(
            total_input=1,
            total_after_filter=1,
            total_returned=1,
            products=[
                ScoredProduct(
                    item_id="p1",
                    score=87,
                    title="Summer Dress",
                    image_url="https://example.com/dress.jpg",
                    product_url="https://shop.com/dress",
                    price=29.99,
                    currency="EUR",
                    country="DE",
                    source="tiktok_shop",
                    sold_count=50000,
                    rating=4.8,
                    trust_label="best_seller",
                    category="dresses",
                    gender="woman",
                    eu_market_fit=True,
                    creator_video=None,
                    score_breakdown={
                        "confidence": 38,
                        "source_signal": 19,
                        "eu_market_fit": 5,
                        "gender_match": 10,
                        "creator_virality": 15,
                    },
                )
            ],
            gender_filter_applied=False,
        ),
        cached=False,
        execution_ms=5,
    )


def test_run_success():
    """POST /product-scorer/run returns 200 with valid input."""
    with patch(
        "SKILLS.C_product_scorer.router._skill.run",
        new_callable=AsyncMock,
        return_value=_make_skill_result(),
    ):
        response = client.post(
            "/run",
            json={
                "items": [
                    {
                        "item_id": "p1",
                        "title": "Dress",
                        "is_fashion": True,
                        "confidence": 0.95,
                    }
                ],
                "params": {"gender": "woman"},
                "n_results": 5,
            },
            headers={"Authorization": "Bearer test-user-001"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["total_returned"] == 1
    assert body["data"]["products"][0]["score"] == 87


def test_run_missing_auth():
    """POST without Authorization header returns 422."""
    response = client.post(
        "/run",
        json={
            "items": [{"item_id": "p1"}],
            "params": {},
        },
    )
    assert response.status_code == 422
