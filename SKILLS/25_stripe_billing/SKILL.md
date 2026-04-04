# Skill 25 -- Stripe Billing

## Description

Server-side Stripe billing management. Zero frontend. Handles subscription
creation, cancellation, plan changes, billing status, and webhook processing.

## Endpoints

### POST /create-subscription (requires auth)

Create a new subscription for the authenticated user.

**Input:**
| Field              | Type  | Required | Description                          |
|--------------------|-------|----------|--------------------------------------|
| `plan`             | `str` | Yes      | "starter", "growth", or "agency"     |
| `payment_method_id`| `str` | Yes      | Stripe payment method ID             |

**Output:** `{ subscription_id, client_secret, status, plan }`

### POST /cancel (requires auth)

Cancel subscription at end of current billing period.

**Input:** Empty body `{}`

### POST /change-plan (requires auth)

Change subscription plan with proration.

**Input:**
| Field      | Type  | Required | Description                          |
|------------|-------|----------|--------------------------------------|
| `new_plan` | `str` | Yes      | "starter", "growth", or "agency"     |

### GET /status (requires auth)

Get current billing status and credit usage.

**Output:**
| Field                | Type   | Description                    |
|----------------------|--------|--------------------------------|
| `plan`               | `str`  | Current plan name              |
| `status`             | `str`  | Subscription status            |
| `image_credits_used` | `int`  | Images generated this period   |
| `image_credits_limit`| `int`  | Image credit limit for plan    |
| `video_credits_used` | `int`  | Videos generated this period   |
| `video_credits_limit`| `int`  | Video credit limit for plan    |
| `current_period_end` | `str`  | ISO datetime of period end     |
| `cancel_at_period_end`| `bool`| Whether cancellation is pending|

### POST /webhook (NO auth)

Stripe webhook endpoint. Uses `stripe.Webhook.construct_event` with raw body
and webhook secret for signature verification.

**Handled events:**
- `invoice.paid` -- reset credits for new billing period
- `customer.subscription.updated` -- sync plan and status
- `customer.subscription.deleted` -- deactivate subscription

## Plans

| Plan    | Images | Videos | Price   |
|---------|--------|--------|---------|
| starter | 50     | 0      | $97/mo  |
| growth  | 200    | 5      | $247/mo |
| agency  | 500    | 15     | $497/mo |

## Authentication

All endpoints except `/webhook` require a Bearer token in the `Authorization`
header.

```
Authorization: Bearer <user_id>
```

## Database Tables

- **subscriptions**: id, user_id, stripe_customer_id, stripe_subscription_id, plan, status, current_period_start, current_period_end, cancel_at_period_end
- **user_credits**: id, user_id, plan, image_credits_used, image_credits_limit, video_credits_used, video_credits_limit, reset_at

## curl Examples

```bash
# Create subscription
curl -X POST http://localhost:8000/stripe-billing/create-subscription \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer user_abc123" \
  -d '{"plan": "growth", "payment_method_id": "pm_xxx"}'

# Check status
curl http://localhost:8000/stripe-billing/status \
  -H "Authorization: Bearer user_abc123"

# Cancel
curl -X POST http://localhost:8000/stripe-billing/cancel \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer user_abc123" \
  -d '{}'

# Change plan
curl -X POST http://localhost:8000/stripe-billing/change-plan \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer user_abc123" \
  -d '{"new_plan": "agency"}'
```
