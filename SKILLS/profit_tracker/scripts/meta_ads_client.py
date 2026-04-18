"""Meta (Facebook + Instagram) daily-spend client.

Returns DailyChannelSpend[] in `reporting_currency` for the whole period.
Fail-soft: on any non-recoverable error the orchestrator skips the channel
and records it under `DataQuality.skipped_channels`.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime
from decimal import Decimal

import httpx

from SKILLS.profit_tracker.scripts.fx import convert
from SKILLS.profit_tracker.scripts.pnl_builder import DailyChannelSpend, Money, Period

logger = logging.getLogger(__name__)

GRAPH_VERSION = "v19.0"


async def fetch_spend(
    *,
    access_token: str,
    ad_account_id: str,
    period: Period,
    reporting_currency: str,
) -> list[DailyChannelSpend]:
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{ad_account_id}/insights"
    params = {
        "access_token": access_token,
        "fields": "date_start,spend,account_currency,impressions,clicks",
        "time_increment": 1,
        "time_range": f'{{"since":"{period.start.isoformat()}","until":"{period.end.isoformat()}"}}',
        "level": "account",
        "action_attribution_windows": '["7d_click","1d_view"]',
    }

    rows: list[dict] = []
    async with httpx.AsyncClient(timeout=20.0) as client:
        cursor_url: str | None = url
        cursor_params: dict | None = params
        while cursor_url:
            resp = await _get_with_retry(client, cursor_url, cursor_params)
            data = resp.json()
            rows.extend(data.get("data") or [])
            paging = data.get("paging") or {}
            cursor_url = paging.get("next")
            cursor_params = None

    out: list[DailyChannelSpend] = []
    for r in rows:
        day = datetime.strptime(r["date_start"], "%Y-%m-%d").date()
        ccy = r.get("account_currency") or reporting_currency
        native = Money(amount=Decimal(str(r.get("spend") or 0)), currency=ccy)
        converted = await convert(native, reporting_currency, day)
        out.append(
            DailyChannelSpend(
                channel="meta",
                day=day,
                spend=converted,
                impressions=int(r.get("impressions") or 0),
                clicks=int(r.get("clicks") or 0),
            )
        )
    return out


async def _get_with_retry(
    client: httpx.AsyncClient, url: str, params: dict | None
) -> httpx.Response:
    delay = 1.0
    for attempt in range(4):
        resp = await client.get(url, params=params)
        if resp.status_code == 200:
            return resp
        payload = _safe_json(resp)
        code = ((payload or {}).get("error") or {}).get("code")
        if code == 190:
            resp.raise_for_status()
        if code == 17 or resp.status_code >= 500:
            await asyncio.sleep(delay)
            delay *= 2
            continue
        resp.raise_for_status()
    resp.raise_for_status()
    return resp  # unreachable


def _safe_json(resp: httpx.Response) -> dict | None:
    try:
        return resp.json()
    except Exception:
        return None
