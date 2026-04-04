"""Tests for the Video Ripper router."""

import importlib

import pytest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

_router_mod = importlib.import_module("SKILLS.03_video_ripper.router")
router = _router_mod.router

_schemas = importlib.import_module("SKILLS.03_video_ripper.schemas")
VideoRipperOutput = _schemas.VideoRipperOutput
RippedVideo = _schemas.RippedVideo

from core.skill_interface import SkillResult

app = FastAPI()
app.include_router(router, prefix="/video-ripper")
client = TestClient(app)


def test_run_success():
    """POST /video-ripper/run returns 200 with ripped video data."""
    mock_output = VideoRipperOutput(
        product_id="prod-1",
        videos_downloaded=1,
        videos=[
            RippedVideo(
                ad_id="v1",
                storage_path="user-1/prod-1/v1.mp4",
                signed_url="https://storage.example.com/signed/v1.mp4",
                duration_seconds=20.0,
                views=150000,
                engagement_rate=0.05,
                hook_end_seconds=3.0,
                cta_start_seconds=15.0,
                thumbnail_url=None,
                source="shop_videos",
            )
        ],
        used_product_details_enrichment=False,
    )
    mock_result = SkillResult(
        success=True,
        data=mock_output,
        cached=False,
        execution_ms=1200,
    )

    with patch(
        "SKILLS.03_video_ripper.router._skill.run",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        resp = client.post(
            "/video-ripper/run",
            json={"product_id": "prod-1", "max_videos": 3},
            headers={"Authorization": "Bearer test-user"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["product_id"] == "prod-1"
    assert body["data"]["videos_downloaded"] == 1
    assert body["data"]["used_product_details_enrichment"] is False


def test_run_missing_auth():
    """POST /video-ripper/run returns 422 when Authorization header is missing."""
    resp = client.post(
        "/video-ripper/run",
        json={"product_id": "prod-1"},
    )
    assert resp.status_code == 422
