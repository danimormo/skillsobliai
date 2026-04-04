import logging

from fastapi import APIRouter, Header, HTTPException, Request

from core.errors import InvalidParamsError, UpstreamError

from SKILLS.stripe_billing.schemas import (
    BillingStatusOutput,
    CancelInput,
    ChangePlanInput,
    CreateSubscriptionInput,
    CreateSubscriptionOutput,
    WebhookOutput,
)
from SKILLS.stripe_billing.service import (
    handle_cancel,
    handle_change_plan,
    handle_create_subscription,
    handle_get_status,
    handle_webhook,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stripe-billing"])


def _extract_user_id(authorization: str) -> str:
    """Extract user_id from Bearer token (placeholder implementation)."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    return token


@router.post("/create-subscription", response_model=CreateSubscriptionOutput)
async def create_subscription_endpoint(
    body: CreateSubscriptionInput,
    authorization: str = Header(...),
) -> CreateSubscriptionOutput:
    """Create a new Stripe subscription."""
    user_id = _extract_user_id(authorization)
    try:
        return await handle_create_subscription(body, user_id)
    except InvalidParamsError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    except UpstreamError as exc:
        raise HTTPException(status_code=502, detail=exc.message) from exc


@router.post("/cancel", response_model=CreateSubscriptionOutput)
async def cancel_endpoint(
    body: CancelInput,
    authorization: str = Header(...),
) -> CreateSubscriptionOutput:
    """Cancel subscription at end of billing period."""
    user_id = _extract_user_id(authorization)
    try:
        return await handle_cancel(body, user_id)
    except InvalidParamsError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    except UpstreamError as exc:
        raise HTTPException(status_code=502, detail=exc.message) from exc


@router.post("/change-plan", response_model=CreateSubscriptionOutput)
async def change_plan_endpoint(
    body: ChangePlanInput,
    authorization: str = Header(...),
) -> CreateSubscriptionOutput:
    """Change subscription plan with proration."""
    user_id = _extract_user_id(authorization)
    try:
        return await handle_change_plan(body, user_id)
    except InvalidParamsError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    except UpstreamError as exc:
        raise HTTPException(status_code=502, detail=exc.message) from exc


@router.get("/status", response_model=BillingStatusOutput)
async def status_endpoint(
    authorization: str = Header(...),
) -> BillingStatusOutput:
    """Get current billing status and credit usage."""
    user_id = _extract_user_id(authorization)
    try:
        return await handle_get_status(user_id)
    except InvalidParamsError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc


@router.post("/webhook", response_model=WebhookOutput)
async def webhook_endpoint(request: Request) -> WebhookOutput:
    """Handle Stripe webhook events. NO auth -- uses Stripe signature verification."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        return await handle_webhook(payload, sig_header)
    except InvalidParamsError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
