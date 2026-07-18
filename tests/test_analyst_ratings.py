#!/usr/bin/env python3
"""
Tests for yfinance_analyst_ratings modern-schema fix (bug #8).

yfinance `.recommendations` is now aggregated counts (period/strongBuy/buy/hold/
sell/strongSell). We select the current '0m' bucket explicitly, coerce counts
robustly, and raise (not silent-zero) on a schema break. Mocks yfinance — no network.

Run:  .venv/bin/python tests/test_analyst_ratings.py
"""
import os, sys
import numpy as np
import pandas as pd
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import scripts.data_fetchers as df_mod
from scripts.data_fetchers import yfinance_analyst_ratings
from scripts.run_deep_dive import _format_analyst_line

_passed = _failed = 0


def check(name, cond):
    global _passed, _failed
    _passed += 1 if cond else 0
    _failed += 0 if cond else 1
    print(f"  {'✓ PASS' if cond else '✗ FAIL'}  {name}")


class FakeTicker:
    def __init__(self, recs):
        self.recommendations = recs


def recs_df(rows):
    """rows: list of dicts with period/strongBuy/buy/hold/sell/strongSell."""
    return pd.DataFrame(rows)


def call(recs):
    # yfinance is imported inside the function, so patch the real module's Ticker.
    with mock.patch("yfinance.Ticker", return_value=FakeTicker(recs)):
        return yfinance_analyst_ratings("TEST")


# ── 1. Happy path: '0m' NOT the first row; numpy-numeric counts ───────
print("\ncurrent '0m' bucket selected explicitly (not iloc[0]):")
recs = recs_df([
    {"period": "-3m", "strongBuy": 1, "buy": 1, "hold": 9, "sell": 5, "strongSell": 3},
    {"period": "-2m", "strongBuy": 2, "buy": 2, "hold": 8, "sell": 4, "strongSell": 2},
    {"period": "0m",  "strongBuy": 6, "buy": 23, "hold": 15, "sell": 2, "strongSell": 1},  # last row!
])
r = call(recs)
check("picks '0m' row (buy=23), not first (buy=1)", r["buy"] == 23)
check("strong_buy from '0m' (6)", r["strong_buy"] == 6)
check("num_analysts = sum (47)", r["num_analysts"] == 47)
check("period preserved ('0m')", r["period"] == "0m")
check("shape matches finnhub (has strong_buy/strong_sell)",
      set(["buy", "hold", "sell", "strong_buy", "strong_sell"]).issubset(r))

# numpy int dtypes (what pandas actually yields)
recs_np = recs_df([{"period": "0m", "strongBuy": np.int64(6), "buy": np.int64(23),
                    "hold": np.int64(15), "sell": np.int64(2), "strongSell": np.int64(1)}])
check("numpy int64 counts coerced fine", call(recs_np)["num_analysts"] == 47)


# ── 2. Malformed counts → raise (no silent zero) ──────────────────────
print("\nmalformed counts raise (not silent-zero):")
def raises(recs):
    try:
        call(recs); return False
    except ValueError:
        return True

check("NaN count → raise", raises(recs_df([{"period": "0m", "strongBuy": np.nan,
      "buy": 23, "hold": 15, "sell": 2, "strongSell": 1}])))
check("negative count → raise", raises(recs_df([{"period": "0m", "strongBuy": -1,
      "buy": 23, "hold": 15, "sell": 2, "strongSell": 1}])))
check("non-integral count → raise", raises(recs_df([{"period": "0m", "strongBuy": 6.5,
      "buy": 23, "hold": 15, "sell": 2, "strongSell": 1}])))
check("zero total → raise", raises(recs_df([{"period": "0m", "strongBuy": 0, "buy": 0,
      "hold": 0, "sell": 0, "strongSell": 0}])))


# ── 3. Schema break / missing bucket → raise ──────────────────────────
print("\nschema break handling:")
check("no 'period' column → raise", raises(pd.DataFrame([{"Firm": "X", "To Grade": "Buy"}])))
check("no '0m' row → raise", raises(recs_df([{"period": "-1m", "strongBuy": 1, "buy": 1,
      "hold": 1, "sell": 1, "strongSell": 1}])))
check("duplicate '0m' rows → raise", raises(recs_df([
    {"period": "0m", "strongBuy": 1, "buy": 1, "hold": 1, "sell": 1, "strongSell": 1},
    {"period": "0m", "strongBuy": 2, "buy": 2, "hold": 2, "sell": 2, "strongSell": 2}])))
check("empty recommendations → raise", raises(pd.DataFrame()))


# ── 4. Formatter renders counts (not firm/grade) ──────────────────────
print("\n_format_analyst_line (yfinance) renders counts:")
line = _format_analyst_line("yfinance", {"buy": 23, "hold": 15, "sell": 2,
                                          "strong_buy": 6, "strong_sell": 1, "period": "0m"})
check("shows Buy/Hold/Sell counts", "29 Buy, 15 Hold, 3 Sell" in line)
check("shows buy% and period", "% buy, 0m" in line)


print(f"\n{'='*54}\n  {_passed} passed, {_failed} failed\n{'='*54}")
sys.exit(1 if _failed else 0)
