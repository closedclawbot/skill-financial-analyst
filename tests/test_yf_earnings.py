#!/usr/bin/env python3
"""
Tests for yfinance_earnings modern-schema fix (bug #10).

`.quarterly_earnings` is gone (returns None) → dead fallback removed. yfinance's
`surprisePercent` is a FRACTION; we compute surprise % ourselves (percent,
consistent with Finnhub + the scoring `surprise_avg > 5` threshold). Mocks
yfinance — no network.

Run:  .venv/bin/python tests/test_yf_earnings.py
"""
import os, sys
import numpy as np
import pandas as pd
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from scripts.data_fetchers import yfinance_earnings

_passed = _failed = 0


def check(name, cond):
    global _passed, _failed
    _passed += 1 if cond else 0
    _failed += 0 if cond else 1
    print(f"  {'✓ PASS' if cond else '✗ FAIL'}  {name}")


class FakeTicker:
    def __init__(self, eh):
        self.earnings_history = eh
    @property
    def quarterly_earnings(self):
        raise AssertionError("quarterly_earnings must NOT be accessed (dead fallback removed)")


def call(eh):
    with mock.patch("yfinance.Ticker", return_value=FakeTicker(eh)):
        return yfinance_earnings("TEST")


# ── happy path: surprise computed as PERCENT (not the fractional field) ──
print("\nsurprise computed as percent:")
eh = pd.DataFrame({
    "epsActual":     [1.94, 2.10, 1.50, 2.01],
    "epsEstimate":   [2.00, 2.00, 2.00, 1.94],
    "epsDifference": [-0.06, 0.10, -0.50, 0.07],
    "surprisePercent": [-0.03, 0.05, -0.25, 0.0346],  # yfinance's FRACTION (ignored)
}, index=["-3q", "-2q", "-1q", "0q"])
r = call(eh)
last = r["earnings"][-1]
check("surprise% is percent (~3.6, not 0.0346)", abs(last["surprisePercent"] - (2.01-1.94)/1.94*100) < 1e-6)
check("surprise% clearly > 1 (percent scale)", last["surprisePercent"] > 3)
check("beat_count = 2 (the two positive surprises)", r["beat_count"] == 2)
check("miss_count = 2", r["miss_count"] == 2)
check("surprise_avg on percent scale (>1 magnitude plausible)", abs(r["surprise_avg"]) > 1)
check("does NOT access quarterly_earnings (no assertion raised)", True)  # reached = not raised


# ── robustness: None/0 estimate, numpy dtypes ─────────────────────────
print("\nrobustness:")
eh2 = pd.DataFrame({
    "epsActual":   [np.float64(2.01), 1.0, 3.0],
    "epsEstimate": [np.float64(1.94), 0.0, None],   # 0 and None estimate → surprise None
}, index=["a", "b", "c"])
r2 = call(eh2)
check("numpy floats handled", abs(r2["earnings"][0]["surprisePercent"] - (2.01-1.94)/1.94*100) < 1e-6)
check("zero estimate → surprise None (no div-by-zero)", r2["earnings"][1]["surprisePercent"] is None)
check("None estimate → surprise None", r2["earnings"][2]["surprisePercent"] is None)
check("only the valid surprise counted", r2["beat_count"] == 1 and r2["miss_count"] == 0)


# ── empty earnings_history → raise cleanly (no AttributeError) ─────────
print("\nempty history:")
def raises(eh):
    try:
        call(eh); return False
    except ValueError:
        return True
    except AttributeError:
        return "ATTR"
check("empty DataFrame → ValueError (not AttributeError)", raises(pd.DataFrame()) is True)
check("None history → ValueError", raises(None) is True)


print(f"\n{'='*54}\n  {_passed} passed, {_failed} failed\n{'='*54}")
sys.exit(1 if _failed else 0)
