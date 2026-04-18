# FX & currency normalisation

Every `Money` that lands inside a `ProfitReport` is in `reporting_currency`
(default `EUR`). Conversion happens as close to the data source as
possible — the P&L math never deals with mixed currencies.

---

## 1. Rate source priority

Implemented in `scripts/fx.py::get_rate(from_ccy, to_ccy, day)`:

1. **Cache** — `fx:{from}:{to}:{YYYY-MM-DD}` in Redis (TTL: 30 days; past
   rates never change). Hit rate is ~100 % after the first run of the
   month.
2. **ECB** — `https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml`
   for today; the archived CSV for historical days. ECB publishes one
   value per business day, in EUR. For non-EUR pairs we do a cross rate:
   `A/B = (EUR/B) / (EUR/A)`.
3. **exchangerate.host** — free mirror that fills ECB weekends/holidays
   (carries forward the previous business-day rate, which is what ECB
   itself does for T+1 settlement).
4. **Fallback** — last known good rate in cache. When we hit this branch
   the day is added to `DataQuality.fx_fallback_days` and a warning is
   emitted.

ECB is authoritative for the reporting_currency we care about (EUR). For
merchants whose reporting currency is not a G10 currency (HUF, RON, PLN,
TRY etc.) the ECB covers all of them; exotic currencies (ARS, VND, NGN)
fall back to exchangerate.host directly.

---

## 2. Weekend / holiday handling

The three ad platforms all report spend on weekends (ads run every day).
ECB does not publish rates on weekends. Policy:

- Saturday & Sunday → use Friday's rate.
- Bank holidays → use the previous publication day's rate.

exchangerate.host returns this correctly; ECB XML does not, so when we
read ECB directly we snap to the last business day ourselves.

---

## 3. Rounding

- All arithmetic uses `Decimal` with `prec = 28`.
- Rounding happens exactly once, at the end of `pnl_builder.build_pnl`,
  using `ROUND_HALF_EVEN` to 2 decimals for display.
- Intermediate rounding is forbidden — summing 10 000 fees pre-rounded
  drifts by ≥€1 vs. post-rounded.

---

## 4. Testing

`scripts/fx.py` exposes an in-memory overlay for tests:

```python
from SKILLS.profit_tracker.scripts import fx
fx.set_test_rates({
    ("USD", "EUR", date(2026, 3, 15)): Decimal("0.92"),
})
```

`test_smoke.py` uses this to run the P&L without network. Don't leave the
overlay set outside of tests — `fx.clear_test_rates()` is called in the
pytest fixture teardown.

---

## 5. Cached data correctness

Because we key the cache by `from:to:day`, past days never need
invalidation — ECB never republishes a historical rate. Today's rate is
refreshed every request with a 6-hour soft TTL. If Redis is unreachable
the client falls back to a process-local `dict` cache; FX never blocks
the P&L.
