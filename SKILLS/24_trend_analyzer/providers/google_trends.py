"""Google Trends provider — interest over time + geo delta + related queries.

Backed by the ``trendspy`` package (moderner, maintained replacement for
``pytrends``). All upstream calls are blocking, so we wrap each in
:func:`asyncio.to_thread`. Calls are serialized (not parallel) to reduce the
chance of Google's anti-bot tripping.

Failure policy
--------------
Google Trends returns HTTP 429 / 403 liberally from datacenter IPs. On any
exception we fall back to whatever is still in the Redis cache (even if
stale from the caller's perspective — we mark ``stale=True`` so the service
can surface a warning).
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime
from typing import Any

from .. import cache
from ..cost_tracker import CostTracker
from ..schemas import GeoInterest, InterestPoint, TrendsSignal

logger = logging.getLogger(__name__)

PROVIDER = "google_trends"

DEFAULT_TIMEFRAME = "today 12-m"
DELTA_RECENT_TIMEFRAME = "today 1-m"
DELTA_REFERENCE_TIMEFRAME = "today 3-m"
TOP_GEO_LIMIT = 5
MAX_RELATED = 10


async def fetch(
    primary_keyword: str,
    cost: CostTracker,
    *,
    timeframe: str = DEFAULT_TIMEFRAME,
    countries: list[str] | None = None,
    no_cache: bool = False,
) -> TrendsSignal:
    """Return a :class:`TrendsSignal` for ``primary_keyword``.

    The ``countries`` filter is currently informational — Google Trends returns
    a global regional distribution by default and we filter to the requested
    set after the fact, which is both cheaper and more robust than per-country
    calls.
    """
    key = _cache_key(primary_keyword, timeframe, countries or [])

    if not no_cache:
        hit = await cache.get(PROVIDER, key)
        if hit is not None:
            return TrendsSignal.model_validate(hit)

    try:
        signal = await _fetch_live(primary_keyword, timeframe, countries or [])
    except Exception as exc:
        logger.warning("google_trends.live_failed kw=%r err=%s", primary_keyword, exc)
        stale = await cache.get_stale(PROVIDER, key)
        if stale is not None:
            sig = TrendsSignal.model_validate(stale)
            sig.stale = True
            return sig
        # Upstream down and nothing cached — return an empty signal rather than
        # failing the whole run. Scoring will fall back to neutral momentum.
        return TrendsSignal(stale=True)

    # Free provider — record a zero-cost entry for traceability only.
    cost.add(provider=PROVIDER, operation="fetch", usd=0.0, note=primary_keyword)

    if not no_cache:
        await cache.set(PROVIDER, key, signal.model_dump(mode="json"))

    return signal


# ── Live fetch ─────────────────────────────────────────────────────────────


async def _fetch_live(
    keyword: str, timeframe: str, countries: list[str]
) -> TrendsSignal:
    from trendspy import Trends  # imported lazily so tests don't need the library

    trends = Trends()

    iot = await asyncio.to_thread(
        trends.interest_over_time, [keyword], timeframe=timeframe
    )
    interest_points = _parse_interest_over_time(iot, keyword)

    geo_recent = await asyncio.to_thread(
        trends.interest_by_region,
        [keyword],
        timeframe=DELTA_RECENT_TIMEFRAME,
        resolution="COUNTRY",
    )
    geo_reference = await asyncio.to_thread(
        trends.interest_by_region,
        [keyword],
        timeframe=DELTA_REFERENCE_TIMEFRAME,
        resolution="COUNTRY",
    )
    geography = _compute_geo_delta(geo_recent, geo_reference, keyword, countries)

    try:
        related = await asyncio.to_thread(trends.related_queries, keyword)
    except Exception as exc:  # related_queries can fail independently
        logger.debug("google_trends.related_failed kw=%r err=%s", keyword, exc)
        related = None

    rising, top = _parse_related(related, keyword)

    return TrendsSignal(
        interest_over_time=interest_points,
        geography=geography,
        related_queries_rising=rising,
        related_queries_top=top,
        stale=False,
    )


# ── Parsers ─────────────────────────────────────────────────────────────────


def _parse_interest_over_time(df: Any, keyword: str) -> list[InterestPoint]:
    """Accept a pandas DataFrame, a dict, or a list-of-dicts."""
    if df is None:
        return []

    records = _to_records(df, keyword)
    points: list[InterestPoint] = []
    for rec in records:
        dt = _coerce_date(rec.get("date") or rec.get("index"))
        val = rec.get(keyword) if keyword in rec else rec.get("value")
        if dt is None or val is None:
            continue
        try:
            points.append(InterestPoint(date=dt, value=max(0, min(100, int(val)))))
        except (TypeError, ValueError):
            continue
    return points


def _compute_geo_delta(
    recent: Any, reference: Any, keyword: str, countries: list[str]
) -> list[GeoInterest]:
    recent_map = _region_map(recent, keyword)
    ref_map = _region_map(reference, keyword)
    if not recent_map:
        return []

    allow = {c.upper() for c in countries} if countries else None

    rows: list[GeoInterest] = []
    for country, current in recent_map.items():
        if allow and country.upper() not in allow:
            continue
        prior = ref_map.get(country, 0)
        denom = max(prior, 1)
        delta_pct = round((current - prior) / denom * 100, 1)
        rows.append(
            GeoInterest(country=country, current_value=int(current), delta_pct=delta_pct)
        )

    rows.sort(key=lambda r: (r.delta_pct, r.current_value), reverse=True)
    return rows[:TOP_GEO_LIMIT]


def _region_map(df: Any, keyword: str) -> dict[str, int]:
    """Return ``{country: interest}`` regardless of the container shape."""
    if df is None:
        return {}
    out: dict[str, int] = {}
    for rec in _to_records(df, keyword):
        country = (
            rec.get("geoName")
            or rec.get("country")
            or rec.get("index")
            or rec.get("name")
        )
        val = rec.get(keyword) if keyword in rec else rec.get("value")
        if not country or val is None:
            continue
        try:
            out[str(country)] = int(val)
        except (TypeError, ValueError):
            continue
    return out


def _parse_related(related: Any, keyword: str) -> tuple[list[str], list[str]]:
    """``related`` can be a dict, nested by keyword, by category (rising/top)."""
    if related is None:
        return [], []

    blob: Any = related
    if isinstance(blob, dict) and keyword in blob:
        blob = blob[keyword]

    rising_src = top_src = None
    if isinstance(blob, dict):
        rising_src = blob.get("rising")
        top_src = blob.get("top")
    elif isinstance(blob, tuple) and len(blob) == 2:
        top_src, rising_src = blob

    return _queries_list(rising_src), _queries_list(top_src)


def _queries_list(source: Any) -> list[str]:
    if source is None:
        return []
    records = _to_records(source, keyword=None)
    queries: list[str] = []
    for rec in records:
        q = rec.get("query") or rec.get("title") or rec.get("topic_title")
        if q:
            queries.append(str(q))
        if len(queries) >= MAX_RELATED:
            break
    return queries


# ── Shape-agnostic conversion helpers ──────────────────────────────────────


def _to_records(obj: Any, keyword: str | None) -> list[dict]:
    """Normalize pandas / dict / list inputs to a list[dict] shape."""
    if obj is None:
        return []

    # pandas DataFrame
    if hasattr(obj, "reset_index") and hasattr(obj, "to_dict"):
        try:
            reset = obj.reset_index()
            return reset.to_dict(orient="records")
        except Exception:
            pass

    if isinstance(obj, list):
        return [r for r in obj if isinstance(r, dict)]

    if isinstance(obj, dict):
        # {country: value, ...} or {date: value, ...}
        if keyword:
            return [{"geoName": k, keyword: v} for k, v in obj.items()]
        return [{"key": k, "value": v} for k, v in obj.items()]

    return []


def _coerce_date(val: Any):
    from datetime import date

    if val is None:
        return None
    if isinstance(val, date):
        return val
    if hasattr(val, "date") and callable(val.date):
        try:
            return val.date()
        except TypeError:
            pass
    if isinstance(val, str):
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(val, fmt).date()
            except ValueError:
                continue
    return None


def _cache_key(keyword: str, timeframe: str, countries: list[str]) -> str:
    country_sig = ",".join(sorted(c.upper() for c in countries))
    payload = f"{keyword.strip().lower()}|{timeframe}|{country_sig}"
    return hashlib.sha1(payload.encode()).hexdigest()
