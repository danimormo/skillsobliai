import logging

import stripe

from core.config import settings

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY

PLAN_LIMITS = {
    "starter": {"images": 50, "videos": 0, "price_usd": 97},
    "growth": {"images": 200, "videos": 5, "price_usd": 247},
    "agency": {"images": 500, "videos": 15, "price_usd": 497},
}

PLAN_PRICE_IDS = {
    "starter": settings.STRIPE_PRICE_STARTER,
    "growth": settings.STRIPE_PRICE_GROWTH,
    "agency": settings.STRIPE_PRICE_AGENCY,
}


def create_customer(email: str, user_id: str) -> stripe.Customer:
    """Create a Stripe customer with metadata linking to our user_id."""
    return stripe.Customer.create(
        email=email,
        metadata={"user_id": user_id},
    )


def create_subscription(
    customer_id: str,
    price_id: str,
    payment_method_id: str,
) -> stripe.Subscription:
    """Create a Stripe subscription with automatic payment settings."""
    # Attach payment method to customer
    stripe.PaymentMethod.attach(payment_method_id, customer=customer_id)
    stripe.Customer.modify(
        customer_id,
        invoice_settings={"default_payment_method": payment_method_id},
    )

    return stripe.Subscription.create(
        customer=customer_id,
        items=[{"price": price_id}],
        payment_settings={
            "payment_method_types": ["card"],
            "save_default_payment_method": "on_subscription",
        },
        expand=["latest_invoice.payment_intent"],
    )


def cancel_subscription(subscription_id: str) -> stripe.Subscription:
    """Cancel a subscription at the end of the current billing period."""
    return stripe.Subscription.modify(
        subscription_id,
        cancel_at_period_end=True,
    )


def change_plan(subscription_id: str, new_price_id: str) -> stripe.Subscription:
    """Change subscription plan with proration."""
    subscription = stripe.Subscription.retrieve(subscription_id)
    return stripe.Subscription.modify(
        subscription_id,
        items=[
            {
                "id": subscription["items"]["data"][0]["id"],
                "price": new_price_id,
            }
        ],
        proration_behavior="create_prorations",
    )
