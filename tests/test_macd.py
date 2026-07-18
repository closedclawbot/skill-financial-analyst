#!/usr/bin/env python3
"""
Tests for the MACD signal/histogram swap fix (bug #3).

Verifies name-based column mapping (robust to column order), the crossover
semantics above AND below the zero line, the tolerant histogram invariant, and
graceful handling of schema drift (missing column).

Run:  .venv/bin/python tests/test_macd.py   (needs pandas + pandas-ta)
"""
import os, sys, math
import numpy as np
import pandas as pd
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import scripts.technical_analysis as tech
from scripts.technical_analysis import compute_technicals, HAS_PANDAS_TA

_passed = _failed = 0


def check(name, cond):
    global _passed, _failed
    _passed += 1 if cond else 0
    _failed += 0 if cond else 1
    print(f"  {'✓ PASS' if cond else '✗ FAIL'}  {name}")


def _ohlcv(n=40):
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    rng = np.random.RandomState(7)
    close = pd.Series(np.linspace(100, 140, n) + np.sin(np.linspace(0, 18, n)) * 3, index=idx)
    return pd.DataFrame({"Open": close.shift(1).fillna(close.iloc[0]),
                         "High": close + 1, "Low": close - 1, "Close": close,
                         "Volume": pd.Series(rng.randint(1_000_000, 3_000_000, n), index=idx)})


def _macd_df(line, hist, signal, order=("MACD", "MACDh", "MACDs")):
    """Build a controlled pandas-ta-style MACD frame; `order` lets us shuffle columns."""
    names = {"MACD": "MACD_12_26_9", "MACDh": "MACDh_12_26_9", "MACDs": "MACDs_12_26_9"}
    vals = {"MACD": [0.0, 0.0, line], "MACDh": [0.0, 0.0, hist], "MACDs": [0.0, 0.0, signal]}
    return pd.DataFrame({names[t]: vals[t] for t in order})


if not HAS_PANDAS_TA:
    print("pandas-ta not available — this test targets the pandas-ta branch. SKIP.")
    sys.exit(0)


# ── 1. Real data: histogram invariant (tolerant) + bullish == line>signal ──
print("\nreal data — invariant + bullish semantics:")
t = compute_technicals(_ohlcv(60), "TEST")
line, sig, hist = t["macd_line"], t["macd_signal"], t["macd_histogram"]
check("histogram ≈ line − signal (abs_tol 2e-4)", math.isclose(hist, line - sig, abs_tol=2e-4))
check("macd_bullish == (line > signal)", t["macd_bullish"] == (line > sig))
# The swap bug would make |signal| and |histogram| interchange; sanity: signal is
# the larger-magnitude EMA of the line, histogram the small residual.
check("|histogram| ≤ |signal| (not swapped)", abs(hist) <= abs(sig) + 2e-4)


# ── 2. Column order shuffled → still mapped BY NAME ───────────────────
print("\nshuffled column order → name-based mapping holds:")
with mock.patch.object(tech.ta, "macd", return_value=_macd_df(1.5, 0.5, 1.0, order=("MACDs", "MACDh", "MACD"))):
    r = compute_technicals(_ohlcv(40), "TEST")
check("macd_line = MACD col (1.5)", math.isclose(r["macd_line"], 1.5, abs_tol=1e-6))
check("macd_signal = MACDs col (1.0)", math.isclose(r["macd_signal"], 1.0, abs_tol=1e-6))
check("macd_histogram = MACDh col (0.5)", math.isclose(r["macd_histogram"], 0.5, abs_tol=1e-6))


# ── 3. Crossover semantics — the swap's actual failure modes ──────────
print("\ncrossover semantics (the cases the swap got wrong):")
# Bullish crossover BELOW zero: line(-0.5) > signal(-0.7) → True; hist = +0.2.
with mock.patch.object(tech.ta, "macd", return_value=_macd_df(-0.5, 0.2, -0.7)):
    r = compute_technicals(_ohlcv(40), "TEST")
check("line>signal below zero → bullish True (bug said False)", r["macd_bullish"] is True)

# Bearish crossover ABOVE zero: line(0.5) < signal(0.7) → False; hist = -0.2.
with mock.patch.object(tech.ta, "macd", return_value=_macd_df(0.5, -0.2, 0.7)):
    r = compute_technicals(_ohlcv(40), "TEST")
check("line<signal above zero → bullish False (bug said True)", r["macd_bullish"] is False)


# ── 4. Schema drift: missing column → None, no crash, no mis-map ──────
print("\nschema drift (missing MACDs column):")
bad = pd.DataFrame({"MACD_12_26_9": [0.0, 0.0, 1.0], "MACDh_12_26_9": [0.0, 0.0, 0.2]})
with mock.patch.object(tech.ta, "macd", return_value=bad):
    r = compute_technicals(_ohlcv(40), "TEST")
check("missing column → macd_line None", r["macd_line"] is None)
check("missing column → macd_signal None", r["macd_signal"] is None)
check("missing column → macd_histogram None", r["macd_histogram"] is None)
check("missing column → macd_bullish None (no crash)", r["macd_bullish"] is None)


print(f"\n{'='*52}\n  {_passed} passed, {_failed} failed\n{'='*52}")
sys.exit(1 if _failed else 0)
