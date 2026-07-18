#!/usr/bin/env python3
"""
Tests for percent formatting units (bug #14).

`_fmt_pct` now always treats input as a FRACTION (×100), fixing both the
already-percent field (dividendYield) that was ×100'd and values ≥ 1 (ROE > 100%,
payout > 100%) that the old `abs<1` heuristic left unscaled. `_fmt_pct_value`
formats an already-percent value unscaled.

Run:  python3 tests/test_fmt_pct.py
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from scripts.data_cache import _fmt_pct, _fmt_pct_value, _format_markdown

_passed = _failed = 0


def check(name, cond):
    global _passed, _failed
    _passed += 1 if cond else 0
    _failed += 0 if cond else 1
    print(f"  {'✓ PASS' if cond else '✗ FAIL'}  {name}")


# ── _fmt_pct: fraction → percent, no magnitude guessing ───────────────
print("\n_fmt_pct (fraction → percent):")
check("0.166 → 16.60%", _fmt_pct(0.166) == "16.60%")
check("high ROE 1.14288 → 114.29% (old heuristic showed '1.14%')", _fmt_pct(1.14288) == "114.29%")
check("payout > 1 (1.5) → 150.00% (was '1.50%')", _fmt_pct(1.5) == "150.00%")
check("negative -0.05 → -5.00%", _fmt_pct(-0.05) == "-5.00%")
check("None → N/A", _fmt_pct(None) == "N/A")


# ── _fmt_pct_value: already-percent, unscaled ─────────────────────────
print("\n_fmt_pct_value (already percent):")
check("KO dividendYield 2.6 → 2.60%", _fmt_pct_value(2.6) == "2.60%")
check("AAPL dividendYield 0.32 → 0.32% (NOT 32%)", _fmt_pct_value(0.32) == "0.32%")
check("None → N/A", _fmt_pct_value(None) == "N/A")


# ── integration: dividends section renders correct units ──────────────
print("\ndividends section (live yfinance units):")
md = _format_markdown("KO", "2026-07-18", {
    "dividends": {"dividend_yield": 2.6, "payout_ratio": 0.648},
})
check("dividend yield shown 2.60% (not 260%)", "Dividend Yield: 2.60%" in md)
check("payout ratio shown 64.80% (fraction ×100)", "Payout Ratio: 64.80%" in md)
check("no 260% mis-scale anywhere", "260.00%" not in md)


print(f"\n{'='*54}\n  {_passed} passed, {_failed} failed\n{'='*54}")
sys.exit(1 if _failed else 0)
