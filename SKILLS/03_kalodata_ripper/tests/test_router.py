import importlib

import pytest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

_router_mod = importlib.import_module("SKILLS.03_kalodata_ripper.router")
router = _router_mod.router

_schemas = importlib.import_module("SKILLS.03_kalodata_ripper.schemas")
KalodataRipperOutput = _schemas.KalodataRipperOutput

from core.skill_interface import SkillResult

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_run_success():
    """POST /kalodata-ripper/run returns 200 with ripped video data."""
    mock_output = KalodataRipperOutput(
        product_id="prod-1",
        videos_downloaded=1,
        videos=[
            {
                "ad_id": "v1",
                "storage_url": "https://storage.example.com/signed/v1.mp4",
                "duration_seconds": 20.0,
                "views": 150000,
                "engagement_rate": 0.05,
                "suggested_hook_end": 3.0,
                "suggested_cta_start": 15.0,
                "thumbnail_url": None,
            }
        ],
    )
    mock_result = SkillResult(
        success=True,
        data=mock_output,
        cached=False,
        execution_ms=1200,
    )

    with patch.object(
        router, "_skill", create=True
    ):
        with patch(
            "SKILLS.03_kalodata_ripper.router._skill.run",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = client.post(
                "/kalodata-ripper/run",
                json={"product_id": "prod-1", "max_videos": 3},
                params={"user_id": "test-user"},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["product_id"] == "prod-1"
    assert body["data"]["videos_downloaded"] == 1


def test_run_validation_error():
    """POST /kalodata-ripper/run returns 422 when required field is missing."""
    resp = client.post(
        "/kalodata-ripper/run",
        json={"max_videos": 3},  # missing product_id
    )
    assert resp.status_code == 422
