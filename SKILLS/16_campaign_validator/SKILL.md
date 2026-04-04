# Skill 16 — Campaign Validator

## Purpose
Validates all campaign parameters before launch. Runs blocking and non-blocking checks against the Meta Graph API and local rules to determine whether a campaign is safe to launch.

## Endpoints
- `POST /run` — Validate campaign parameters.

## Input
| Field | Type | Default | Description |
|---|---|---|---|
| ad_account_id | str | required | Meta Ad Account ID |
| pixel_id | str | required | Meta Pixel ID |
| campaign_name | str | required | Campaign name |
| daily_budget_usd | float | required | Daily budget in USD |
| target_countries | list[str] | required | ISO country codes |
| creative_image_urls | list[str] | required | Creative image URLs |
| ad_copy | str | required | Ad body text |
| ad_headline | str | required | Ad headline |
| destination_url | str | required | Landing page URL |
| product_price | float | required | Product selling price |
| product_cost | float | required | Product cost |
| shipping_cost | float | 4.0 | Shipping cost |

## Output
| Field | Type | Description |
|---|---|---|
| can_launch | bool | True if all blocking checks passed |
| checks | list[ValidationCheck] | Individual check results |
| warnings | list[str] | Non-blocking warnings |
| break_even_roas | float | Calculated break-even ROAS |
| summary | str | Human-readable summary |

## Checks
| Check | Blocking | Description |
|---|---|---|
| ad_account_active | Yes | Ad account status is ACTIVE (1) |
| pixel_active | Yes | Pixel is available and has fired |
| funding_source | Yes | Payment method configured |
| budget_check | Yes | daily_budget >= 5.0 |
| creative_check | Yes | At least 1 image URL |
| copy_check | Yes | ad_copy and headline not empty |
| url_check | Yes | destination_url starts with https |
| margin_check | No | Break-even ROAS calculation |

## External Dependencies
- Meta Graph API (`META_BASE_URL` / `META_API_VERSION`)
- Supabase (user_integrations table)

## Cache
None — validation must always be real-time.
