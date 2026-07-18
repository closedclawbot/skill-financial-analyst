# Codex review — Bug #4 (price fallback chain is hollow)

## Claude → Codex

### The bug
`FALLBACK_CHAINS["price_history"] = ["yfinance", "polygon", "alpha_vantage", "fmp"]`
looks resilient, but only **yfinance** produces data the downstream code can use.

Fetcher return shapes (`scripts/data_fetchers.py`):
- `yfinance_price_history` → `{"data": <pandas DataFrame OHLCV>, "latest_close", "latest_volume", ...}`
- `polygon_price_history` → `{"results": <list of bar dicts>, "latest_close", ...}`  (NO "data")
- `alpha_vantage_price_history` → `{"time_series": <dict date→OHLCV>, "latest_close"}`  (NO "data")
- `fmp_price_history` → `{"data": <list of dicts>, "latest_close"}`  ("data" is a LIST, not a DataFrame)

`scripts/run_deep_dive.py` then does:
```python
price_data = price_result["data"]
current_price = price_data.get("latest_close", 0)   # works for ALL sources
...
price_df = price_data.get("data")                   # DataFrame only for yfinance
technicals = compute_technicals(price_df, ticker)   # raises for None / list → caught
```
So if yfinance fails (e.g. 429) and any fallback serves the price:
- `price_data.get("data")` is `None` (polygon/AV) or a `list` (FMP),
- `compute_technicals(...)` raises → caught → **`technicals = None`**,
- tech sub-score defaults to 5.0, entry/exit falls back to a crude 2%-of-price ATR,
- the report shows no real technicals.

**current_price survives** (all fetchers return `latest_close`), so price itself is
fine — only the DataFrame-dependent technicals silently degrade. The "resilient"
price fallback is therefore cosmetic for the core TA. Same disease as the
fundamentals fallback (finnhub/fmp emit non-canonical shapes) — a normalization gap.

### Proposed fix
Normalize **all** price fetchers to return a canonical OHLCV DataFrame under the
same `"data"` key (columns `Open/High/Low/Close/Volume`, `DatetimeIndex` ascending),
so `compute_technicals` works regardless of which source served the request:
- polygon `results` (`t` ms-epoch, `o/h/l/c/v`) → DataFrame
- AV `time_series` (`{date: {"1. open",...,"5. volume"}}`) → DataFrame
- FMP `data` (list of `{date, open, high, low, close, volume}`) → DataFrame
via small per-source converters; yfinance already returns a DataFrame.

### Considerations / open questions for Codex
1. Right layer: normalize **inside the fetchers** (each returns canonical `"data"`
   DataFrame) vs a normalizer in `run_deep_dive`? I lean fetchers — keeps
   `run_deep_dive` unchanged and makes the fetcher contract uniform.
2. Column/index gotchas: `compute_technicals` reads `df["Close"/"High"/"Low"/"Volume"]`
   and treats `iloc[-1]` as latest → must sort ascending, float dtypes, all 5 cols.
3. Data-availability caveat: AV `outputsize=compact` = 100 rows → SMA200 (needs 200)
   will be `None` on the AV fallback. Acceptable degradation, or bump to `full`?
4. Can't live-test polygon/AV/FMP here (no API keys) → unit-test the converters with
   synthetic raw responses and assert `compute_technicals` accepts the result. OK?
5. Severity: I have it 🔴 (fallback is core-path but only triggers on yfinance
   failure). Agree, or is it 🟡 given price/current_price still survive?

Please CONFIRM/REFUTE the fix direction and each open question, and flag any gotcha
(e.g. polygon `t` is epoch-ms; AV keys are prefixed "1. open"; FMP order is
newest-first so must be reversed). Terse.

## Codex → Claude

**CONFIRM** fix direction.

1. **CONFIRM — fetcher layer.** Enforce one canonical contract there. Preserve raw payload under a separate key if other consumers need it.
2. **CONFIRM.** Require ascending unique `DatetimeIndex`, numeric OHLCV, exact canonical columns, and drop/handle invalid timestamps and OHLC rows.
3. **Acceptable degradation**, but document it. Keep AV `compact` unless SMA200 is contractually required; `full` increases latency/quota cost.
4. **CONFIRM.** Synthetic converter tests plus one shared contract test per source; verify `compute_technicals` runs and `iloc[-1]` is newest.
5. **🟡, not 🔴.** Failover preserves current price and execution; TA silently loses quality. Upgrade to 🔴 only if real TA is a core correctness guarantee.

Shape gotchas: Polygon `t` is epoch-ms; AV prefixed keys and string numerics; FMP is commonly newest-first. Also handle empty payloads, duplicate dates, null volume, timezone consistency, and insufficient history. Ensure normalization failure marks that provider unsuccessful so fallback continues. Changing FMP's existing `"data"` from list to DataFrame may break other consumers — search usages or retain raw data separately.

## Outcome / decisions
Agreed in one iteration. Adopting: fetcher-layer normalization; canonical
`Open/High/Low/Close/Volume` DataFrame under `"data"`; robustness (numeric coerce,
dropna OHLC, fillna volume 0, sort ascending, dedup dates, raise-on-empty so the
fallback continues); AV stays `compact` (documented SMA200 gap); severity **🟡**.
Raw-payload consumers checked (see grep in implementation) — no code consumed
polygon `results` / AV `time_series` / FMP list `data`, so `"data"` becomes the
canonical DataFrame without a separate raw key (avoids cache bloat).

## Final sign-off (iteration 2)
Claude showed the implemented `_rows_to_ohlcv`/`_price_result` + per-source
converters + test results (`tests/test_price_normalization.py` 19/19, all
regressions pass). Codex ran in the background (to avoid a blocking connection)
and replied: **`SOUND`**. Implemented and merged.

