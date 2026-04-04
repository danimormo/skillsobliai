from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from SKILLS.video_generator.router import router
from SKILLS.video_generator.schemas import VideoGeneratorOutput
from core.skill_interface import SkillResult

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def _make_skill_result() -> SkillResult[VideoGeneratorOutput]:
    return SkillResult(
        success=True,
        data=VideoGeneratorOutput(
            job_id="job-001",
            video_storage_path="creative-videos/user/job-001/video.mp4",
            video_signed_url="https://storage.example.com/signed-video",
            thumbnail_signed_url=None,
            duration_seconds=5.0,
            aspect_ratio="9:16",
            file_size_mb=2.5,
            credits_used=1,
            credits_remaining=49,
            vertex_operation_name="projects/test/locations/us-central1/operations/op-123",
        ),
        cached=False,
        execution_ms=15000,
    )


def test_run_success():
    """POST /run returns 200 with valid input."""
    with patch(
        "SKILLS.video_generator.router._skill.run",
        new_callable=AsyncMock,
        return_value=_make_skill_result(),
    ):
        response = client.post(
            "/run",
            json={
                "product_title": "Organic Matcha Powder",
                "source_image_url": "https://example.com/product.jpg",
                "aspect_ratio": "9:16",
            },
            headers={"Authorization": "Bearer test-user-001"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["duration_seconds"] == 5.0
    assert "op-123" in body["data"]["vertex_operation_name"]


def test_run_missing_auth():
    """POST without Authorization header returns 422."""
    response = client.post(
        "/run",
        json={
            "product_title": "Test Product",
            "source_image_url": "https://example.com/img.jpg",
        },
    )
    assert response.status_code == 422
