"""Google Ads daily-spend client.

Uses the GAQL REST endpoint. Expects a refresh-token already minted by the
parent app; swaps for an access token at runtime and caches it in-process
for 50 minutes.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from decimal import Decimal

import httpx

from SKILLS.profit_tracker.scripts.fx import convert
from SKILLS.profit_tracker.scripts.pnl_builder import DailyChannelSpend, Money, Period

logger = logging.getLogger(__name__)

API_VERSION = "v17"
TOKEN_URL = "https://oauth2.googleapis.com/token"

_ACCESS_CACHE: dict[str, tuple[str, float]] = {}


async def fetch_spend(
    *,
    developer_token: str,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    login_customer_id: str,
    customer_id: str,
    period: Period,
    reporting_currency: str,
) -> list[DailyChannelSpend]:
    access_token = await _get_access_token(client_id, client_secret, refresh_token)
    query = (
        "SELECT segments.date, metrics.cost_micros, metrics.impressions, "
        "metrics.clicks, metrics.conversions, customer.currency_code "
        "FROM customer "
        f"WHERE segments.date BETWEEN '{period.start.isoformat()}' "
        f"AND '{period.end.isoformat()}'"
    )
    url = f"https://googleads.googleapis.com/{API_VERSION}/customers/{customer_id}/googleAds:search"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "developer-token": developer_token,
        "login-customer-id": login_customer_id,
        "Content-Type": "application/json",
    }

    rows: list[dict] = []
    page_token: str | None = None
    async with httpx.AsyncClient(timeout=20.0) as client:
        while True:
            body: dict = {"query": query}
            if page_token:
                body["pageToken"] = page_token
            resp = await _post_with_retry(client, url, headers, body)
            data = resp.json()
            rows.extend(data.get("results") or [])
            page_token = data.get("nextPageToken")
            if not page_token:
                break

    out: list[DailyChannelSpend] = []
    for r in rows:
        seg = r.get("segments") or {}
        metrics = r.get("metrics") or {}
        cust = r.get("customer") or {}
        day = datetime.strptime(seg["date"], "%Y-%m-%d").date()
        micros = Decimal(str(metrics.get("costMicros") or metrics.get("cost_micros") or 0))
        native = Money(
            amount=micros / Decimal("1000000"),
            currency=cust.get("currencyCode") or reporting_currency,
        )
        converted = await convert(native, reporting_currency, day)
        out.append(
            DailyChannelSpend(
                channel="google",
                day=day,
                spend=converted,
                impressions=int(metrics.get("impressions") or 0),
                clicks=int(metrics.get("clicks") or 0),
                purchases=int(Decimal(str(metrics.get("conversions") or 0))),
            )
        )
    return out


async def _get_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    now = time.time()
    cached = _ACCESS_CACHE.get(refresh_token)
    if cached and cached[1] > now:
        return cached[0]
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        data = resp.json()
    token = data["access_token"]
    _ACCESS_CACHE[refresh_token] = (token, now + 50 * 60)
    return token


async def _post_with_retry(
    client: httpx.AsyncClient, url: str, headers: dict, body: dict
) -> httpx.Response:
    delay = 1.0
    for attempt in range(4):
        resp = await client.post(url, headers=headers, json=body)
        if resp.status_code == 200:
            return resp
        if resp.status_code in (429, 500, 502, 503, 504):
            await asyncio.sleep(delay)
            delay *= 2
            continue
        resp.raise_for_status()
    resp.raise_for_status()
    return resp
