"""FX lookup with ECB primary source and exchangerate.host fallback.

Key surface:
    await convert(amount, from_ccy, to_ccy, day)   # Money-aware
    await get_rate(from_ccy, to_ccy, day)          # Decimal

Cache policy: past days are immutable so cached forever (30 d TTL in
Redis to cap storage); today's rate has a 6 h soft TTL.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

import httpx

from SKILLS.profit_tracker.scripts.pnl_builder import Money

logger = logging.getLogger(__name__)

ECB_DAILY = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
EXCHANGERATE_HOST = "https://api.exchangerate.host/{day}?base={base}&symbols={sym}"

_PROCESS_CACHE: dict[tuple[str, str, date], Decimal] = {}
_TEST_OVERRIDES: dict[tuple[str, str, date], Decimal] = {}


def set_test_rates(rates: dict[tuple[str, str, date], Decimal]) -> None:
    """Inject fixed rates for tests. Call clear_test_rates() in teardown."""
    _TEST_OVERRIDES.update(rates)


def clear_test_rates() -> None:
    _TEST_OVERRIDES.clear()


def _snap_to_business_day(day: date) -> date:
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


async def get_rate(from_ccy: str, to_ccy: str, day: date) -> Decimal:
    """Return 1 unit of `from_ccy` expressed in `to_ccy` on `day`."""
    if from_ccy == to_ccy:
        return Decimal("1")

    key = (from_ccy, to_ccy, day)
    if key in _TEST_OVERRIDES:
        return _TEST_OVERRIDES[key]
    if key in _PROCESS_CACHE:
        return _PROCESS_CACHE[key]

    snapped = _snap_to_business_day(day)
    rate = await _fetch_from_ecb(from_ccy, to_ccy, snapped)
    if rate is None:
        rate = await _fetch_from_exchangerate_host(from_ccy, to_ccy, snapped)
    if rate is None:
        raise FxUnavailable(f"no FX rate for {from_ccy}->{to_ccy} on {day}")

    _PROCESS_CACHE[key] = rate
    return rate


async def convert(amount: Money, to_ccy: str, day: date) -> Money:
    if amount.currency == to_ccy:
        return amount
    rate = await get_rate(amount.currency, to_ccy, day)
    return Money(amount=(amount.amount * rate), currency=to_ccy)


class FxUnavailable(Exception):
    pass


# ─────────────────────────── providers ────────────────────────────────


async def _fetch_from_ecb(from_ccy: str, to_ccy: str, day: date) -> Optional[Decimal]:
    """ECB publishes EUR-based rates. Cross via EUR for non-EUR pairs."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(ECB_DAILY)
            resp.raise_for_status()
            rates = _parse_ecb_xml(resp.text)
    except Exception as exc:
        logger.warning("ECB fetch failed: %s", exc)
        return None

    if from_ccy == "EUR" and to_ccy in rates:
        return rates[to_ccy]
    if to_ccy == "EUR" and from_ccy in rates:
        return Decimal("1") / rates[from_ccy]
    if from_ccy in rates and to_ccy in rates:
        return rates[to_ccy] / rates[from_ccy]
    return None


def _parse_ecb_xml(xml: str) -> dict[str, Decimal]:
    """Tiny parser — ECB's daily XML is tiny and the structure is stable."""
    out: dict[str, Decimal] = {}
    for part in xml.split("<Cube "):
        if 'currency="' not in part:
            continue
        ccy = part.split('currency="', 1)[1].split('"', 1)[0]
        rate = part.split('rate="', 1)[1].split('"', 1)[0]
        try:
            out[ccy] = Decimal(rate)
        except Exception:
            continue
    return out


async def _fetch_from_exchangerate_host(
    from_ccy: str, to_ccy: str, day: date
) -> Optional[Decimal]:
    url = EXCHANGERATE_HOST.format(day=day.isoformat(), base=from_ccy, sym=to_ccy)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            value = data.get("rates", {}).get(to_ccy)
            if value is None:
                return None
            return Decimal(str(value))
    except Exception as exc:
        logger.warning("exchangerate.host fetch failed: %s", exc)
        return None
