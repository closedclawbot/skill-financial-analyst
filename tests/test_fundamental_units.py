#!/usr/bin/env python3
"""
Tests for the ROE / Debt-to-Equity unit fix (bugs #1 / #2 + sibling heuristics).

Uses REAL yfinance raw values pulled live (2026-07): the old `<1`/`>10`
heuristics mis-scored high-ROE and low-debt names; the explicit per-field
conversion fixes the edge cases while leaving normal names unchanged.

Run:  python3 tests/test_fundamental_units.py   (no deps, no network)
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from scripts.scoring import _score_fundamental, _pct, _de_ratio

_passed = _failed = 0


def check(name, cond):
    global _passed, _failed
    _passed += 1 if cond else 0
    _failed += 0 if cond else 1
    print(f"  {'✓ PASS' if cond else '✗ FAIL'}  {name}")


def factor(fund, key):
    return _score_fundamental(fund)["factor_details"][key]


# ── unit converters ──────────────────────────────────────────────────
print("\nunit converters:")
check("_pct(1.41) == 141", _pct(1.41) == 141.0)
check("_pct(None) is None", _pct(None) is None)
check("_de_ratio(79.5) == 0.795", _de_ratio(79.5) == 0.795)
check("_de_ratio(None) is None", _de_ratio(None) is None)


# ── #1 ROE: high-ROE names were scored ~1% (score 4); now correct ─────
print("\nROE (returnOnEquity is a fraction):")
nvda_roe = factor({"roe": 1.14288}, "roe")   # 114% — was read as 1.14% → score 4
check("NVDA ROE 1.14 → 114.3%", nvda_roe["value"] == 114.3)
check("NVDA ROE → score 9 (was 4)", nvda_roe["score"] == 9)
aapl_roe = factor({"roe": 1.4147099}, "roe")  # 141%
check("AAPL ROE 1.41 → score 9 (was 4)", aapl_roe["score"] == 9)
ko_roe = factor({"roe": 0.43372002}, "roe")   # 43% — was already correct
check("KO ROE 0.43 → 43.4% (unchanged)", ko_roe["value"] == 43.4)
check("KO ROE → score 9 (behavior preserved)", ko_roe["score"] == 9)


# ── #2 D/E: low-debt names were "extremely leveraged"; now correct ────
print("\nDebt/Equity (debtToEquity is a percent of the ratio):")
nvda_de = factor({"debt_to_equity": 6.555}, "debt_to_equity")   # ratio 0.066
check("NVDA D/E 6.5 → ratio 0.07", nvda_de["value"] == 0.07)
check("NVDA D/E → score 9 'very low debt' (was 2 'extremely leveraged')", nvda_de["score"] == 9)
mnst_de = factor({"debt_to_equity": 1.082}, "debt_to_equity")   # ratio 0.011
check("MNST D/E 1.08 → score 9 (was 5 'high debt')", mnst_de["score"] == 9)
aapl_de = factor({"debt_to_equity": 79.548}, "debt_to_equity")  # ratio 0.795
check("AAPL D/E 79.5 → ratio 0.8 (unchanged)", aapl_de["value"] == 0.8)
check("AAPL D/E → score 7 (behavior preserved)", aapl_de["score"] == 7)
ko_de = factor({"debt_to_equity": 124.943}, "debt_to_equity")   # ratio 1.25
check("KO D/E 124.9 → ratio 1.25 (unchanged)", ko_de["value"] == 1.25)


# ── siblings: growth / margin fractions, explicit ×100 ────────────────
print("\nsibling fraction fields (growth / margin):")
rg = factor({"revenue_growth": 0.166}, "revenue_growth")
check("revenueGrowth 0.166 → 16.6% (unchanged for normal)", rg["value"] == 16.6)
# The heuristic misfired on hyper-growth (fraction ≥ 5); now explicit.
rg_hyper = factor({"revenue_growth": 6.0}, "revenue_growth")   # 600% growth
check("revenueGrowth 6.0 → 600% (was mis-read as 6%)", rg_hyper["value"] == 600.0)
pm = factor({"profit_margin": 0.27152}, "profit_margin")
check("profitMargins 0.27 → 27.2% (unchanged)", pm["value"] == 27.2)


print(f"\n{'='*54}\n  {_passed} passed, {_failed} failed\n{'='*54}")
sys.exit(1 if _failed else 0)
