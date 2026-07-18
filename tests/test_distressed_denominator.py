#!/usr/bin/env python3
"""
Tests for the negative-equity denominator guard (bugs #19 + #20).

A negative shareholder equity produces TWO degenerate metrics that the old
scorer rewarded with 9/10:
  • P/B < 0  (priceToBook negative ⇔ equity negative) was caught by `pb < 1`
    → 9/10 "deep value". Now `pb <= 0` → 2 "negative book value". (#19)
  • ROE = NetIncome/Equity explodes when equity is negative/tiny (FGMC 1028%)
    → 9/10 "exceptional". Now, when equity is negative (pb <= 0), ROE → 5
    "unreliable — denominator artifact". A legitimate buyback-driven high ROE
    with POSITIVE equity (AAPL ~141%) still scores 9. (#20)

Discovered on a real run: `run_deep_dive.py FGMC` (de-SPAC, merged with BOXABL).

Run:  python3 tests/test_distressed_denominator.py   (no deps, no network)
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from scripts.scoring import _score_fundamental

_passed = _failed = 0


def check(name, cond):
    global _passed, _failed
    _passed += 1 if cond else 0
    _failed += 0 if cond else 1
    print(f"  {'✓ PASS' if cond else '✗ FAIL'}  {name}")


def factor(fund, key):
    return _score_fundamental(fund)["factor_details"][key]


# ── #19 — P/B negative-equity guard ───────────────────────────────────
print("\n#19 P/B (negative book value):")
fgmc_pb = factor({"pb_ratio": -2075.0}, "pb_ratio")
check("FGMC P/B -2075 → score 2 (was 9)", fgmc_pb["score"] == 2)
check("FGMC P/B -2075 → 'Negative book value' note",
      "Negative book value" in fgmc_pb["rating_note"])
check("P/B exactly 0 → score 2 (degenerate)", factor({"pb_ratio": 0.0}, "pb_ratio")["score"] == 2)
# behavior preserved for positive equity
check("P/B 0.5 (<1, positive) → score 9 (unchanged)", factor({"pb_ratio": 0.5}, "pb_ratio")["score"] == 9)
check("P/B 1.5 → score 7 (unchanged)", factor({"pb_ratio": 1.5}, "pb_ratio")["score"] == 7)
check("P/B 40 (very expensive) → score 2 (unchanged)", factor({"pb_ratio": 40.0}, "pb_ratio")["score"] == 2)


# ── #20 — ROE tied to equity sign ─────────────────────────────────────
print("\n#20 ROE (denominator artifact under negative equity):")
# FGMC: negative equity (pb<=0) + huge ROE → unreliable, neutral 5
fgmc_roe = factor({"pb_ratio": -2075.0, "roe": 10.288}, "roe")
check("FGMC ROE 1028% + neg equity → score 5 (was 9)", fgmc_roe["score"] == 5)
check("FGMC ROE → 'unreliable' note", "unreliable" in fgmc_roe["rating_note"].lower())
check("FGMC ROE value still shown 1028.8%", fgmc_roe["value"] == 1028.8)
# AAPL-like: POSITIVE equity + high ROE (buyback-driven) stays 9
check("AAPL ROE 141% + positive P/B 40 → score 9 (legit high ROE)",
      factor({"pb_ratio": 40.0, "roe": 1.4147099}, "roe")["score"] == 9)
# pb=None → existing ROE behavior preserved (guard must NOT fire)
check("ROE 141% + pb=None → score 9 (unchanged; guard off)",
      factor({"roe": 1.4147099}, "roe")["score"] == 9)
check("ROE 43% + pb=None → score 9 (unchanged)", factor({"roe": 0.43372}, "roe")["score"] == 9)
# negative equity + NORMAL positive ROE is still an artifact → neutralized
check("neg equity + ROE 25% → score 5 (still artifact, not 8)",
      factor({"pb_ratio": -5.0, "roe": 0.25}, "roe")["score"] == 5)


# ── arithmetic pin: negative-equity fundamentals score strictly lower ──
print("\narithmetic (negative-equity fundamental score):")
_fgmc_like = {
    "pe_ratio": 69.17, "pb_ratio": -2075.0, "revenue_growth": None,
    "earnings_growth": -0.325, "profit_margin": -0.001, "free_cash_flow": -1_000_000,
    "roe": 10.288, "debt_to_equity": None,
}
neg = _score_fundamental(_fgmc_like)["fundamental_score"]
# same vector but with a healthy positive equity (pb 1.5) and no ROE artifact
_healthy = dict(_fgmc_like, pb_ratio=1.5)
pos = _score_fundamental(_healthy)["fundamental_score"]
check("negative-equity fundamental score < positive-equity variant", neg < pos)
# pin the exact arithmetic Codex predicted for the FGMC vector: fundamental → 3.5
check("FGMC-like fundamental score pinned at 3.5 (was ~4.6 with two 9/10 artifacts)", neg == 3.5)
# pin the exact delta: pb 9→2 (-7) and roe 9→5 (-4) vs the pb<1/roe>30 path
# both variants share all other factors, so the gap is purely the two guards.
print(f"    (neg-equity fundamental score = {neg}, positive-equity variant = {pos}, delta = {round(pos-neg,3)})")


print(f"\n{'='*54}\n  {_passed} passed, {_failed} failed\n{'='*54}")
sys.exit(1 if _failed else 0)
