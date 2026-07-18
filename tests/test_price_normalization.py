#!/usr/bin/env python3
"""
Tests for canonical OHLCV normalization across price providers (bug #4).

Each fallback provider (polygon/AV/FMP) must return the SAME canonical DataFrame
under "data" that yfinance does, so compute_technicals() works no matter who
served the request. Mocks HTTP + key lookup — no network.

Run:  .venv/bin/python tests/test_price_normalization.py
"""
import os, sys
import pandas as pd
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import scripts.data_fetchers as df_mod
from scripts.data_fetchers import (
    polygon_price_history, alpha_vantage_price_history, fmp_price_history, _OHLCV_COLS,
)
from scripts.technical_analysis import compute_technicals

_passed = _failed = 0


def check(name, cond):
    global _passed, _failed
    _passed += 1 if cond else 0
    _failed += 0 if cond else 1
    print(f"  {'✓ PASS' if cond else '✗ FAIL'}  {name}")


class FakeResp:
    def __init__(self, data):
        self._d = data
    def json(self):
        return self._d
    def raise_for_status(self):
        pass


_DATES = pd.date_range("2024-01-01", periods=30, freq="B")
_CLOSE = [100.0 + i for i in range(30)]  # ascending 100..129


def _polygon_payload():
    results = [{"t": int(d.value // 10**6), "o": c - 0.5, "h": c + 1, "l": c - 1,
                "c": c, "v": 1_000_000 + i} for i, (d, c) in enumerate(zip(_DATES, _CLOSE))]
    results[5]["v"] = None                       # null volume → filled 0
    results.append(dict(results[-1]))            # duplicate last date → deduped
    return {"resultsCount": len(results), "results": results}


def _av_payload():  # newest-first dict, STRING values, prefixed keys
    ts = {d.strftime("%Y-%m-%d"): {"1. open": str(c - 0.5), "2. high": str(c + 1),
                                    "3. low": str(c - 1), "4. close": str(c),
                                    "5. volume": str(1_000_000 + i)}
          for i, (d, c) in enumerate(zip(_DATES, _CLOSE))}
    return {"Time Series (Daily)": ts}


def _fmp_payload():  # list, NEWEST-FIRST
    recs = [{"date": d.strftime("%Y-%m-%d"), "open": c - 0.5, "high": c + 1,
             "low": c - 1, "close": c, "volume": 1_000_000 + i}
            for i, (d, c) in enumerate(zip(_DATES, _CLOSE))]
    return list(reversed(recs))


def _run(fetcher, payload, key_name):
    with mock.patch.object(df_mod, "get_api_key", return_value="KEY"), \
         mock.patch("requests.get", return_value=FakeResp(payload)):
        return fetcher("TEST")


def _assert_canonical(label, res):
    d = res["data"]
    check(f"{label}: data is a DataFrame", isinstance(d, pd.DataFrame))
    check(f"{label}: columns == OHLCV", list(d.columns) == _OHLCV_COLS)
    check(f"{label}: index ascending", d.index.is_monotonic_increasing)
    check(f"{label}: latest_close is newest (129.0)", res["latest_close"] == 129.0)
    # The contract that matters: compute_technicals must accept it and produce a score.
    t = compute_technicals(d, "TEST")
    check(f"{label}: compute_technicals runs (tech_score present)", "tech_score" in t)
    check(f"{label}: technicals see newest close as latest", t["latest_close"] == 129.0)


print("\npolygon (epoch-ms t, null volume, duplicate date):")
_assert_canonical("polygon", _run(polygon_price_history, _polygon_payload(), "polygon"))

print("\nalpha_vantage (prefixed string keys/values):")
_assert_canonical("AV", _run(alpha_vantage_price_history, _av_payload(), "alpha_vantage"))

print("\nfmp (newest-first list → reordered ascending):")
_assert_canonical("FMP", _run(fmp_price_history, _fmp_payload(), "fmp"))


# ── normalization failure → fetcher raises so fallback continues ──────
print("\nempty/garbage payload → raises (fallback continues):")
raised = False
try:
    _run(polygon_price_history, {"resultsCount": 1, "results": [{"t": None}]}, "polygon")
except Exception:
    raised = True
check("polygon with no usable rows raises", raised)


print(f"\n{'='*54}\n  {_passed} passed, {_failed} failed\n{'='*54}")
sys.exit(1 if _failed else 0)
