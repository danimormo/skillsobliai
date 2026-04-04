import logging
from datetime import datetime, timezone

import stripe

from core.config import settings
from core.errors import InvalidParamsError, UpstreamError
from core.supabase_client import get_supabase

from SKILLS.stripe_billing.api_client import (
    PLAN_LIMITS,
    PLAN_PRICE_IDS,
    cancel_subscription as stripe_cancel,
    change_plan as stripe_change_plan,
    create_customer,
    create_subscription as stripe_create_sub,
)
from SKILLS.stripe_billing.schemas import (
    BillingStatusOutput,
    CancelInput,
    ChangePlanInput,
    CreateSubscriptionInput,
    CreateSubscriptionOutput,
    WebhookOutput,
)

logger = logging.getLogger(__name__)

SKILL_NAME = "stripe-billing"


def _get_or_create_stripe_customer(user_id: str) -> str:
    """Get existing Stripe customer_id from DB or create a new one."""
    supabase = get_supabase()
    result = (
        supabase.table("subscriptions")
        .select("stripe_customer_id")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if result.data and result.data[0].get("stripe_customer_id"):
        return result.data[0]["stripe_customer_id"]

    # Create new customer (use user_id as email placeholder)
    customer = create_customer(email=f"{user_id}@placeholder.com", user_id=user_id)
    return customer.id


async def handle_create_subscription(
    input: CreateSubscriptionInput, user_id: str
) -> CreateSubscriptionOutput:
    """Create a new Stripe subscription for the user."""
    plan = input.plan.lower()
    if plan not in PLAN_LIMITS:
        raise InvalidParamsError(
            message=f"Invalid plan '{input.plan}'. Must be one of: starter, growth, agency",
            skill=SKILL_NAME,
            code="INVALID_PLAN",
        )

    price_id = PLAN_PRICE_IDS[plan]
    limits = PLAN_LIMITS[plan]

    try:
        customer_id = _get_or_create_stripe_customer(user_id)
        subscription = stripe_create_sub(
            customer_id=customer_id,
            price_id=price_id,
            payment_method_id=input.payment_method_id,
        )
    except stripe.error.StripeError as exc:
        logger.error("Stripe error creating subscription: %s", exc)
        raise UpstreamError(
            message=f"Stripe error: {exc.user_message or str(exc)}",
            skill=SKILL_NAME,
            code="STRIPE_ERROR",
        ) from exc

    # Extract client_secret if 3DS is needed
    client_secret = None
    latest_invoice = subscription.get("latest_invoice")
    if isinstance(latest_invoice, dict):
        payment_intent = latest_invoice.get("payment_intent")
        if isinstance(payment_intent, dict):
            client_secret = payment_intent.get("client_secret")

    # Persist to Supabase
    supabase = get_supabase()
    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        supabase.table("subscriptions").upsert(
            {
                "user_id": user_id,
                "stripe_customer_id": customer_id,
                "stripe_subscription_id": subscription.id,
                "plan": plan,
                "status": subscription.status,
                "current_period_start": datetime.fromtimestamp(
                    subscription.current_period_start, tz=timezone.utc
                ).isoformat(),
                "current_period_end": datetime.fromtimestamp(
                    subscription.current_period_end, tz=timezone.utc
                ).isoformat(),
                "cancel_at_period_end": subscription.cancel_at_period_end,
            },
            on_conflict="user_id",
        ).execute()

        supabase.table("user_credits").upsert(
            {
                "user_id": user_id,
                "plan": plan,
                "image_credits_used": 0,
                "image_credits_limit": limits["images"],
                "video_credits_used": 0,
                "video_credits_limit": limits["videos"],
                "reset_at": now_iso,
            },
            on_conflict="user_id",
        ).execute()
    except Exception:
        logger.exception("Failed to persist subscription to Supabase")

    return CreateSubscriptionOutput(
        subscription_id=subscription.id,
        client_secret=client_secret,
        status=subscription.status,
        plan=plan,
    )


async def handle_cancel(input: CancelInput, user_id: str) -> CreateSubscriptionOutput:
    """Cancel subscription at period end."""
    supabase = get_supabase()
    result = (
        supabase.table("subscriptions")
        .select("stripe_subscription_id, plan")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise InvalidParamsError(
            message="No active subscription found",
            skill=SKILL_NAME,
            code="NO_SUBSCRIPTION",
        )

    sub_id = result.data[0]["stripe_subscription_id"]
    plan = result.data[0]["plan"]

    try:
        subscription = stripe_cancel(sub_id)
    except stripe.error.StripeError as exc:
        raise UpstreamError(
            message=f"Stripe error: {exc.user_message or str(exc)}",
            skill=SKILL_NAME,
            code="STRIPE_ERROR",
        ) from exc

    # Update DB
    try:
        supabase.table("subscriptions").update(
            {"cancel_at_period_end": True, "status": subscription.status}
        ).eq("user_id", user_id).execute()
    except Exception:
        logger.exception("Failed to update cancellation in Supabase")

    return CreateSubscriptionOutput(
        subscription_id=sub_id,
        client_secret=None,
        status=subscription.status,
        plan=plan,
    )


async def handle_change_plan(input: ChangePlanInput, user_id: str) -> CreateSubscriptionOutput:
    """Change the user's subscription plan."""
    new_plan = input.new_plan.lower()
    if new_plan not in PLAN_LIMITS:
        raise InvalidParamsError(
            message=f"Invalid plan '{input.new_plan}'. Must be one of: starter, growth, agency",
            skill=SKILL_NAME,
            code="INVALID_PLAN",
        )

    supabase = get_supabase()
    result = (
        supabase.table("subscriptions")
        .select("stripe_subscription_id")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise InvalidParamsError(
            message="No active subscription found",
            skill=SKILL_NAME,
            code="NO_SUBSCRIPTION",
        )

    sub_id = result.data[0]["stripe_subscription_id"]
    new_price_id = PLAN_PRICE_IDS[new_plan]
    new_limits = PLAN_LIMITS[new_plan]

    try:
        subscription = stripe_change_plan(sub_id, new_price_id)
    except stripe.error.StripeError as exc:
        raise UpstreamError(
            message=f"Stripe error: {exc.user_message or str(exc)}",
            skill=SKILL_NAME,
            code="STRIPE_ERROR",
        ) from exc

    # Update DB
    try:
        supabase.table("subscriptions").update(
            {"plan": new_plan, "status": subscription.status}
        ).eq("user_id", user_id).execute()

        supabase.table("user_credits").update(
            {
                "plan": new_plan,
                "image_credits_limit": new_limits["images"],
                "video_credits_limit": new_limits["videos"],
            }
        ).eq("user_id", user_id).execute()
    except Exception:
        logger.exception("Failed to update plan change in Supabase")

    return CreateSubscriptionOutput(
        subscription_id=sub_id,
        client_secret=None,
        status=subscription.status,
        plan=new_plan,
    )


async def handle_get_status(user_id: str) -> BillingStatusOutput:
    """Get billing status from subscriptions + user_credits tables."""
    supabase = get_supabase()

    sub_result = (
        supabase.table("subscriptions")
        .select("plan, status, current_period_end, cancel_at_period_end")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )

    credits_result = (
        supabase.table("user_credits")
        .select("image_credits_used, image_credits_limit, video_credits_used, video_credits_limit")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )

    if not sub_result.data:
        raise InvalidParamsError(
            message="No subscription found for this user",
            skill=SKILL_NAME,
            code="NO_SUBSCRIPTION",
        )

    sub = sub_result.data[0]
    credits = credits_result.data[0] if credits_result.data else {}

    return BillingStatusOutput(
        plan=sub.get("plan", ""),
        status=sub.get("status", ""),
        image_credits_used=credits.get("image_credits_used", 0),
        image_credits_limit=credits.get("image_credits_limit", 0),
        video_credits_used=credits.get("video_credits_used", 0),
        video_credits_limit=credits.get("video_credits_limit", 0),
        current_period_end=sub.get("current_period_end"),
        cancel_at_period_end=sub.get("cancel_at_period_end", False),
    )


async def handle_webhook(payload: bytes, sig_header: str) -> WebhookOutput:
    """Verify Stripe webhook signature and process event."""
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError as exc:
        logger.warning("Invalid webhook signature: %s", exc)
        raise InvalidParamsError(
            message="Invalid webhook signature",
            skill=SKILL_NAME,
            code="INVALID_SIGNATURE",
        ) from exc

    event_type = event["type"]
    processed = False

    try:
        if event_type == "invoice.paid":
            processed = _handle_invoice_paid(event)
        elif event_type == "customer.subscription.updated":
            processed = _handle_subscription_updated(event)
        elif event_type == "customer.subscription.deleted":
            processed = _handle_subscription_deleted(event)
        else:
            logger.info("Unhandled webhook event type: %s", event_type)
    except Exception:
        logger.exception("Error processing webhook event %s", event_type)

    return WebhookOutput(
        received=True,
        event_type=event_type,
        processed=processed,
    )


def _handle_invoice_paid(event: dict) -> bool:
    """Reset credits on successful invoice payment (new billing period)."""
    invoice = event["data"]["object"]
    subscription_id = invoice.get("subscription")
    if not subscription_id:
        return False

    supabase = get_supabase()
    sub_result = (
        supabase.table("subscriptions")
        .select("user_id, plan")
        .eq("stripe_subscription_id", subscription_id)
        .limit(1)
        .execute()
    )
    if not sub_result.data:
        logger.warning("No subscription found for stripe_subscription_id=%s", subscription_id)
        return False

    user_id = sub_result.data[0]["user_id"]
    plan = sub_result.data[0]["plan"]
    limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["starter"])
    now_iso = datetime.now(timezone.utc).isoformat()

    supabase.table("user_credits").update(
        {
            "image_credits_used": 0,
            "image_credits_limit": limits["images"],
            "video_credits_used": 0,
            "video_credits_limit": limits["videos"],
            "reset_at": now_iso,
        }
    ).eq("user_id", user_id).execute()

    logger.info("Reset credits for user %s (plan=%s)", user_id, plan)
    return True


def _handle_subscription_updated(event: dict) -> bool:
    """Sync subscription status and plan from Stripe."""
    subscription = event["data"]["object"]
    subscription_id = subscription.get("id")

    supabase = get_supabase()
    sub_result = (
        supabase.table("subscriptions")
        .select("user_id")
        .eq("stripe_subscription_id", subscription_id)
        .limit(1)
        .execute()
    )
    if not sub_result.data:
        return False

    user_id = sub_result.data[0]["user_id"]

    # Determine plan from price
    items = subscription.get("items", {}).get("data", [])
    price_id = items[0]["price"]["id"] if items else None
    plan = None
    for plan_name, pid in PLAN_PRICE_IDS.items():
        if pid == price_id:
            plan = plan_name
            break

    update_data = {
        "status": subscription.get("status"),
        "cancel_at_period_end": subscription.get("cancel_at_period_end", False),
        "current_period_end": datetime.fromtimestamp(
            subscription.get("current_period_end", 0), tz=timezone.utc
        ).isoformat(),
    }
    if plan:
        update_data["plan"] = plan

    supabase.table("subscriptions").update(update_data).eq("user_id", user_id).execute()

    logger.info("Synced subscription for user %s", user_id)
    return True


def _handle_subscription_deleted(event: dict) -> bool:
    """Deactivate subscription when deleted in Stripe."""
    subscription = event["data"]["object"]
    subscription_id = subscription.get("id")

    supabase = get_supabase()
    sub_result = (
        supabase.table("subscriptions")
        .select("user_id")
        .eq("stripe_subscription_id", subscription_id)
        .limit(1)
        .execute()
    )
    if not sub_result.data:
        return False

    user_id = sub_result.data[0]["user_id"]

    supabase.table("subscriptions").update(
        {"status": "canceled", "cancel_at_period_end": False}
    ).eq("user_id", user_id).execute()

    logger.info("Deactivated subscription for user %s", user_id)
    return True
