# Skill 15 — Campaign Launcher

## Purpose
Launches Meta advertising campaigns via Manus AI. Handles the full flow: submitting the campaign configuration to Manus, polling until the task completes, verifying the campaign exists on Meta Graph API, and persisting results to the database.

## Endpoints
- `POST /run` — Launch a new campaign.

## Input
| Field | Type | Default | Description |
|---|---|---|---|
| shop_domain | str | required | Shopify store domain |
| campaign_name | str | required | Name for the campaign |
| daily_budget_usd | float | required | Daily budget in USD (min 5.00) |
| target_countries | list[str] | ["IT"] | ISO country codes |
| target_age_min | int | 18 | Minimum targeting age |
| target_age_max | int | 65 | Maximum targeting age |
| pixel_id | str | required | Meta Pixel ID |
| ad_account_id | str | required | Meta Ad Account ID |
| creative_image_urls | list[str] | required | At least one image URL |
| creative_video_url | str or null | None | Optional video creative |
| ad_copy | str | required | Ad body text |
| ad_headline | str | required | Ad headline |
| ad_cta | str | "SHOP_NOW" | Call-to-action button |
| destination_url | str | required | Landing page URL |
| roas_target | float | 2.5 | Target ROAS |
| roas_kill_threshold | float | 1.0 | Kill-switch ROAS threshold |
| spend_kill_limit_usd | float | 30.0 | Kill-switch spend limit |

## Output
| Field | Type | Description |
|---|---|---|
| campaign_db_id | str | Internal database ID |
| meta_campaign_id | str | Meta campaign ID |
| meta_adset_id | str | Meta ad set ID |
| meta_ad_id | str | Meta ad ID |
| campaign_name | str | Campaign name |
| status | str | Campaign status |
| daily_budget_usd | float | Budget |
| manus_task_id | str | Manus task ID |
| launched_at | str | ISO timestamp |

## External Dependencies
- Manus AI API (`MANUS_BASE_URL`)
- Meta Graph API (`META_BASE_URL` / `META_API_VERSION`)
- Supabase (user_integrations, campaigns tables)

## Cache
None — write operation.
