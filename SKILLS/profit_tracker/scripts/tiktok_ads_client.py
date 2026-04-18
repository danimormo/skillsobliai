"""TikTok Ads daily-spend client."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from decimal import Decimal

import httpx

from SKILLS.profit_tracker.scripts.fx import convert
from SKILLS.profit_tracker.scripts.pnl_builder import DailyChannelSpend, Money, Period

logger = logging.getLogger(__name__)

BASE_URL = "https://business-api.tiktok.com/open_api/v1.3"


async def fetch_spend(
    *,
    access_token: str,
    advertiser_id: str,
    period: Period,
    reporting_currency: str,
) -> list[DailyChannelSpend]:
    headers = {
        "Access-Token": access_token,
        "Content-Type": "application/json",
    }
    currency = await _fetch_currency(access_token, advertiser_id) or reporting_currency

    all_rows: list[dict] = []
    page = 1
    async with httpx.AsyncClient(timeout=20.0) as client:
        while True:
            body = {
                "advertiser_id": advertiser_id,
                "report_type": "BASIC",
                "data_level": "AUCTION_ADVERTISER",
                "dimensions": ["advertiser_id", "stat_time_day"],
                "metrics": ["spend", "impressions", "clicks", "complete_payment"],
                "start_date": period.start.isoformat(),
                "end_date": period.end.isoformat(),
                "page": page,
                "page_size": 1000,
            }
            resp = await _post_with_retry(
                client, f"{BASE_URL}/report/integrated/get/", headers, body
            )
            data = resp.json()
            rows = ((data.get("data") or {}).get("list") or [])
            all_rows.extend(rows)
            page_info = (data.get("data") or {}).get("page_info") or {}
            total_pages = int(page_info.get("total_page") or 1)
            if page >= total_pages:
                break
            page += 1

    out: list[DailyChannelSpend] = []
    for r in all_rows:
        dims = r.get("dimensions") or {}
        metrics = r.get("metrics") or {}
        day_str = dims.get("stat_time_day")
        if not day_str:
            continue
        day = datetime.strptime(day_str[:10], "%Y-%m-%d").date()
        native = Money(
            amount=Decimal(str(metrics.get("spend") or 0)),
            currency=currency,
        )
        converted = await convert(native, reporting_currency, day)
        out.append(
            DailyChannelSpend(
                channel="tiktok",
                day=day,
                spend=converted,
                impressions=int(metrics.get("impressions") or 0),
                clicks=int(metrics.get("clicks") or 0),
                purchases=int(Decimal(str(metrics.get("complete_payment") or 0))),
            )
        )
    return out


async def _fetch_currency(access_token: str, advertiser_id: str) -> str | None:
    headers = {"Access-Token": access_token}
    params = {"advertiser_ids": f'["{advertiser_id}"]'}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{BASE_URL}/advertiser/info/", headers=headers, params=params
            )
            resp.raise_for_status()
            data = resp.json()
            info = ((data.get("data") or {}).get("list") or [{}])[0]
            return info.get("currency")
    except Exception as exc:
        logger.warning("tiktok advertiser/info failed: %s", exc)
        return None


async def _post_with_retry(
    client: httpx.AsyncClient, url: str, headers: dict, body: dict
) -> httpx.Response:
    delay = 1.0
    for attempt in range(4):
        resp = await client.post(url, headers=headers, json=body)
        if resp.status_code == 200:
            data = resp.json()
            code = data.get("code")
            if code == 0:
                return resp
            if code == 51021:
                await asyncio.sleep(delay)
                delay *= 2
                continue
            resp.raise_for_status()
        if resp.status_code in (429, 500, 502, 503, 504):
            await asyncio.sleep(delay)
            delay *= 2
            continue
        resp.raise_for_status()
    resp.raise_for_status()
    return resp
