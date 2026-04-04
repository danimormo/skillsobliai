from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from SKILLS.theme_configurator.router import router
from SKILLS.theme_configurator.schemas import ThemeConfiguratorOutput
from core.skill_interface import SkillResult

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def _make_skill_result() -> SkillResult[ThemeConfiguratorOutput]:
    return SkillResult(
        success=True,
        data=ThemeConfiguratorOutput(
            shop_domain="test-store.myshopify.com",
            theme_id="12345",
            theme_name="Dawn",
            settings_modified=["primary_color", "secondary_color"],
            success=True,
        ),
        cached=False,
        execution_ms=250,
    )


def test_run_success():
    """POST /theme-configurator/run returns 200 with valid input."""
    with patch(
        "SKILLS.theme_configurator.router._skill.run",
        new_callable=AsyncMock,
        return_value=_make_skill_result(),
    ):
        response = client.post(
            "/run",
            json={
                "shop_domain": "test-store.myshopify.com",
                "primary_color": "#111111",
            },
            headers={"Authorization": "Bearer test-user-001"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["theme_id"] == "12345"


def test_run_missing_auth():
    """POST without Authorization header returns 422."""
    response = client.post(
        "/run",
        json={
            "shop_domain": "test-store.myshopify.com",
        },
    )
    assert response.status_code == 422
