from pydantic import BaseModel


class CreateSubscriptionInput(BaseModel):
    plan: str  # "starter" | "growth" | "agency"
    payment_method_id: str


class CreateSubscriptionOutput(BaseModel):
    subscription_id: str
    client_secret: str | None = None
    status: str
    plan: str


class BillingStatusOutput(BaseModel):
    plan: str
    status: str
    image_credits_used: int
    image_credits_limit: int
    video_credits_used: int
    video_credits_limit: int
    current_period_end: str | None = None
    cancel_at_period_end: bool


class CancelInput(BaseModel):
    pass  # empty, uses user from auth


class ChangePlanInput(BaseModel):
    new_plan: str


class WebhookOutput(BaseModel):
    received: bool
    event_type: str
    processed: bool
