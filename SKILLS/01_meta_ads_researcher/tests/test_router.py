from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from SKILLS.01_meta_ads_researcher.router import router
from SKILLS.01_meta_ads_researcher.schemas import MetaAdsResearchOutput
from core.skill_interface import SkillResult

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def _make_skill_result() -> SkillResult[MetaAdsResearchOutput]:
    return SkillResult(
        success=True,
        data=MetaAdsResearchOutput(
            total_ads=0,
            ads=[],
            search_terms=["test"],
            countries=["IT"],
        ),
        cached=False,
        execution_ms=42,
    )


def test_run_success():
    """POST /meta-ads-researcher/run returns 200 with valid input."""
    with patch(
        "SKILLS.01_meta_ads_researcher.router._skill.run",
        new_callable=AsyncMock,
        return_value=_make_skill_result(),
    ):
        response = client.post(
            "/meta-ads-researcher/run",
            json={
                "search_terms": ["test keyword"],
                "countries": ["IT"],
                "active_only": True,
                "limit_per_term": 10,
            },
            headers={"Authorization": "Bearer test-user-001"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["total_ads"] == 0


def test_run_validation_error():
    """POST with empty search_terms returns 422."""
    response = client.post(
        "/meta-ads-researcher/run",
        json={
            "search_terms": [],
            "countries": ["IT"],
        },
        headers={"Authorization": "Bearer test-user-001"},
    )
    # Pydantic will reject empty list when field is required with max_length
    # FastAPI returns 422 for validation errors
    assert response.status_code == 422


def test_run_missing_auth():
    """POST without Authorization header returns 422 (missing required header)."""
    response = client.post(
        "/meta-ads-researcher/run",
        json={
            "search_terms": ["test"],
            "countries": ["IT"],
        },
    )
    assert response.status_code == 422
