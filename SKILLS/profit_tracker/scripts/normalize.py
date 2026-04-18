"""Period + FX normalisation helpers.

`resolve_period` accepts the natural-language presets exposed in the tool
schema (`last_7d`, `last_30d`, `last_90d`, `mtd`, `ytd`) as well as an
explicit `{"start", "end"}` dict, and returns a canonical `Period`.

`normalize_money` converts any `Money` into the reporting currency using
the daily rate for the order/spend date.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from SKILLS.profit_tracker.scripts.fx import convert
from SKILLS.profit_tracker.scripts.pnl_builder import Money, Period


def resolve_period(period: Any, today: date | None = None, tz: str = "Europe/Rome") -> Period:
    """Turn a period spec into an inclusive/inclusive Period.

    Accepted inputs:
      - str: "last_7d", "last_30d", "last_90d", "mtd", "ytd", "yesterday"
      - dict: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
      - Period: returned unchanged
    """
    today = today or date.today()

    if isinstance(period, Period):
        _validate(period)
        return period

    if isinstance(period, dict):
        start = _parse_date(period["start"])
        end = _parse_date(period["end"])
        p = Period(start=start, end=end, tz=tz)
        _validate(p)
        return p

    if isinstance(period, str):
        preset = period.strip().lower()
        if preset == "yesterday":
            d = today - timedelta(days=1)
            return Period(start=d, end=d, tz=tz)
        if preset == "mtd":
            return Period(start=today.replace(day=1), end=today, tz=tz)
        if preset == "ytd":
            return Period(start=date(today.year, 1, 1), end=today, tz=tz)
        if preset.startswith("last_") and preset.endswith("d"):
            n = int(preset[len("last_"):-1])
            if n <= 0 or n > 730:
                raise ValueError(f"period out of range: {preset}")
            end = today - timedelta(days=1)
            start = end - timedelta(days=n - 1)
            return Period(start=start, end=end, tz=tz)

    raise ValueError(f"unrecognised period spec: {period!r}")


def _parse_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(value, "%Y-%m-%d").date()


def _validate(p: Period) -> None:
    if p.end < p.start:
        raise ValueError(f"period end {p.end} is before start {p.start}")


async def normalize_money(amount: Money, to_ccy: str, day: date) -> Money:
    """FX-convert a Money into the reporting currency, using `day`'s rate."""
    return await convert(amount, to_ccy, day)
