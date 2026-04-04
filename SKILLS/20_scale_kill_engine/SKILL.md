# Skill 20 -- Scale / Kill Engine

## Description

Evaluates ROAS-based rules to automatically scale, kill (pause), or duplicate
ad campaigns. Actions are executed via Manus AI and campaign state is updated
in the database.

## Endpoint

```
POST /scale-kill-engine/run
```

### Authentication

Pass a Bearer token in the `Authorization` header.

```
Authorization: Bearer <user_id>
```

## Input

| Field              | Type     | Required | Default | Description                                |
|--------------------|----------|----------|---------|--------------------------------------------|
| `campaign_db_id`   | `str`    | Yes      | --      | Internal campaign ID.                      |
| `current_roas`     | `float`  | Yes      | --      | Latest computed ROAS.                      |
| `current_spend_usd`| `float`  | Yes      | --      | Latest spend in USD.                       |
| `roas_history`     | `dict[]` | Yes      | --      | Historical ROAS entries `[{roas, date}]`.  |
| `custom_rules`     | `dict`   | No       | `{}`    | Override default thresholds.               |

### Default Rules

| Key                        | Default | Description                              |
|----------------------------|---------|------------------------------------------|
| `scale_threshold`          | `2.5`   | Min ROAS to trigger scale.               |
| `scale_increase_pct`       | `20`    | Budget increase percentage on scale.     |
| `scale_consecutive_days`   | `2`     | Required consecutive days above threshold.|
| `kill_threshold`           | `1.0`   | ROAS below this triggers kill.           |
| `kill_min_spend_usd`       | `30.0`  | Minimum spend before kill is considered. |
| `duplicate_threshold`      | `4.0`   | Min ROAS to trigger duplicate.           |
| `duplicate_consecutive_days`| `5`    | Required consecutive days for duplicate. |

## Output

| Field                | Type    | Description                                 |
|----------------------|---------|---------------------------------------------|
| `campaign_db_id`     | `str`   | Campaign that was evaluated.                |
| `action`             | `str`   | `"scale"`, `"kill"`, `"duplicate"`, `"hold"`|
| `reason`             | `str`   | Human-readable explanation.                 |
| `previous_budget_usd`| `float?`| Budget before the action.                  |
| `new_budget_usd`     | `float?`| Budget after the action (scale only).      |
| `manus_task_id`      | `str?`  | Manus task ID if action was dispatched.    |
| `executed`           | `bool`  | Whether the action was successfully run.   |

## Decision Logic

1. **Kill**: `current_roas < kill_threshold` AND `current_spend_usd > kill_min_spend_usd`
2. **Duplicate**: `current_roas > duplicate_threshold` for N consecutive days
3. **Scale**: `current_roas > scale_threshold` for N consecutive days (+20% budget)
4. **Hold**: No conditions met

## curl Example

```bash
curl -X POST http://localhost:8000/scale-kill-engine/run \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer user_abc123" \
  -d '{
    "campaign_db_id": "camp-001",
    "current_roas": 3.2,
    "current_spend_usd": 150.0,
    "roas_history": [
      {"roas": 3.0, "date": "2026-04-02"},
      {"roas": 3.4, "date": "2026-04-03"},
      {"roas": 3.2, "date": "2026-04-04"}
    ]
  }'
```

## Caching

No caching -- decisions are always computed fresh from the latest data.
