from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from SKILLS.pdp_builder.router import router
from SKILLS.pdp_builder.schemas import PDPBuilderOutput, PDPSections
from core.skill_interface import SkillResult

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def _make_skill_result() -> SkillResult[PDPBuilderOutput]:
    return SkillResult(
        success=True,
        data=PDPBuilderOutput(
            pdp_id="test-pdp-001",
            sections=PDPSections(
                headlines=["Headline 1"],
                subheadline="Sub",
                benefit_bullets=["Bullet"],
                description_long="Long desc.",
                faq=[],
                urgency_text="Hurry!",
                cta_text="Buy Now",
            ),
            copy_angle="benefit",
            language="en",
            word_count=8,
        ),
        cached=False,
        execution_ms=100,
    )


def test_run_success():
    """POST /pdp-builder/run returns 200 with valid input."""
    with patch(
        "SKILLS.pdp_builder.router._skill.run",
        new_callable=AsyncMock,
        return_value=_make_skill_result(),
    ):
        response = client.post(
            "/run",
            json={
                "product_title": "Test Product",
                "price": 19.99,
            },
            headers={"Authorization": "Bearer test-user-001"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["pdp_id"] == "test-pdp-001"


def test_run_missing_auth():
    """POST without Authorization header returns 422."""
    response = client.post(
        "/run",
        json={
            "product_title": "Test Product",
            "price": 19.99,
        },
    )
    assert response.status_code == 422
