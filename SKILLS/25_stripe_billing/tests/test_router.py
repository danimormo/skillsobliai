from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from SKILLS.stripe_billing.router import router
from SKILLS.stripe_billing.schemas import (
    BillingStatusOutput,
    CreateSubscriptionOutput,
)

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_create_subscription_success():
    """POST /create-subscription returns 200 with valid input."""
    mock_result = CreateSubscriptionOutput(
        subscription_id="sub_test123",
        client_secret=None,
        status="active",
        plan="growth",
    )
    with patch(
        "SKILLS.stripe_billing.router.handle_create_subscription",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        response = client.post(
            "/create-subscription",
            json={
                "plan": "growth",
                "payment_method_id": "pm_test123",
            },
            headers={"Authorization": "Bearer test-user-001"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["subscription_id"] == "sub_test123"
    assert body["plan"] == "growth"


def test_status_missing_auth():
    """GET /status without Authorization header returns 422."""
    response = client.get("/status")
    assert response.status_code == 422
