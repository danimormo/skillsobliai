# Skill 18 -- ROAS Monitor

## Description

Reads real-time ROAS (Return on Ad Spend) data from the Meta Graph API for all
active campaigns belonging to a user. Saves snapshots to the `roas_snapshots`
table for historical tracking.

## Endpoint

```
POST /roas-monitor/run
```

### Authentication

Pass a Bearer token in the `Authorization` header. The token is used as the
user identifier.

```
Authorization: Bearer <user_id>
```

## Input

| Field           | Type   | Required | Default | Description                        |
|-----------------|--------|----------|---------|------------------------------------|
| `user_id`       | `str?` | No       | `null`  | Override user from auth context.   |
| `force_refresh` | `bool` | No       | `false` | Reserved for future use.           |

## Output

| Field               | Type                   | Description                              |
|---------------------|------------------------|------------------------------------------|
| `campaigns_checked` | `int`                  | Number of active campaigns evaluated.    |
| `snapshots_saved`   | `int`                  | Number of snapshots persisted to DB.     |
| `actions_triggered` | `int`                  | Number of automated actions triggered.   |
| `results`           | `CampaignROASResult[]` | Per-campaign ROAS breakdown.             |
| `monitored_at`      | `str`                  | ISO timestamp of the monitor run.        |

### CampaignROASResult object

| Field              | Type   | Description                                |
|--------------------|--------|--------------------------------------------|
| `campaign_db_id`   | `str`  | Internal campaign ID.                      |
| `meta_campaign_id` | `str`  | Meta campaign ID.                          |
| `campaign_name`    | `str`  | Human-readable campaign name.              |
| `roas`             | `float`| Computed ROAS (revenue / spend).           |
| `spend_usd`        | `float`| Total spend in USD.                        |
| `revenue_usd`      | `float`| Total purchase revenue in USD.             |
| `impressions`      | `int`  | Total impressions.                         |
| `clicks`           | `int`  | Total clicks.                              |
| `conversions`      | `int`  | Total purchase conversions.                |
| `action_triggered` | `str?` | Action taken (scale/kill/duplicate/null).  |

## curl Example

```bash
curl -X POST http://localhost:8000/roas-monitor/run \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer user_abc123" \
  -d '{
    "force_refresh": false
  }'
```

## Caching

No caching -- ROAS data is always fetched in real-time from the Meta Graph API.
