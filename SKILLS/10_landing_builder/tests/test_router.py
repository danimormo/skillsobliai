from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from SKILLS.landing_builder.router import router
from SKILLS.landing_builder.schemas import LandingBuilderOutput, LandingSection
from core.skill_interface import SkillResult

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def _make_skill_result() -> SkillResult[LandingBuilderOutput]:
    return SkillResult(
        success=True,
        data=LandingBuilderOutput(
            landing_id="test-landing-001",
            sections=[
                LandingSection(
                    type="hero",
                    headline="Test Headline",
                    body="Test body.",
                    cta_text="Buy Now",
                )
            ],
            total_word_count=5,
            language="en",
        ),
        cached=False,
        execution_ms=100,
    )


def test_run_success():
    """POST /landing-builder/run returns 200 with valid input."""
    with patch(
        "SKILLS.landing_builder.router._skill.run",
        new_callable=AsyncMock,
        return_value=_make_skill_result(),
    ):
        response = client.post(
            "/run",
            json={
                "product_title": "Test Product",
                "product_description": "A great product",
                "price": 19.99,
                "target_audience": "Everyone",
                "main_benefit": "Saves time",
                "cta_destination_url": "https://example.com/buy",
            },
            headers={"Authorization": "Bearer test-user-001"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["landing_id"] == "test-landing-001"


def test_run_missing_auth():
    """POST without Authorization header returns 422."""
    response = client.post(
        "/run",
        json={
            "product_title": "Test Product",
            "product_description": "A great product",
            "price": 19.99,
            "target_audience": "Everyone",
            "main_benefit": "Saves time",
            "cta_destination_url": "https://example.com/buy",
        },
    )
    assert response.status_code == 422
