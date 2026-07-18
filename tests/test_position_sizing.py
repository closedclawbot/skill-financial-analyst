#!/usr/bin/env python3
"""
Tests for risk/capital/concentration/liquidity position sizing (bug #11).

Verifies the constraint model, unit pinning, and the invalid-stop guard.
Run:  .venv/bin/python tests/test_position_sizing.py   (no deps)
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from scripts.entry_exit import _compute_position_sizes

_passed = 0
_failed = 0


def check(name, cond):
    global _passed, _failed
    _passed += 1 if cond else 0
    _failed += 0 if cond else 1
    print(f"  {'✓ PASS' if cond else '✗ FAIL'}  {name}")


def one(entry, stop, account=10_000, **kw):
    """Size a single (entry, account) cell and return its leaf dict."""
    sizes = _compute_position_sizes([entry], stop, account_sizes=(account,), **kw)
    return sizes["aggressive"][f"${account:,}"]


# ── 1. Capital-limited: the original 500%-of-account bug ──────────────
print("\ncapital cap kills the 500% bug ($500 stock, tight stop, $10k):")
leaf = one(500.0, 498.0)  # risk/share $2 → risk wants 100 shares = $50k
check("shares capped to what fits capital (20)", leaf["shares"] == 20)
check("notional == $10,000 (not $50,000)", leaf["notional"] == 10_000.0)
check("portfolio_pct == 100 (never 500)", leaf["portfolio_pct"] == 100.0)
check("portfolio_pct never exceeds 100% × leverage", leaf["portfolio_pct"] <= 100.0)
check("binding = capital", leaf["binding_constraints"] == ["capital"])
check("risk constraint still recorded (100)", leaf["constraints"]["risk"]["shares"] == 100)
check("planned_loss_at_stop = 20 × $2 = $40", leaf["planned_loss_at_stop"] == 40.0)
check("risk_budget = 2% of $10k = $200", leaf["risk_budget"] == 200.0)


# ── 2. Risk-limited: cheap stock, plenty of capital ───────────────────
print("\nrisk cap binds ($50 stock, $5 risk/share, $10k):")
leaf = one(50.0, 45.0)  # risk_budget 200 / 5 = 40; capital 10000/50 = 200
check("shares = 40 (risk-limited)", leaf["shares"] == 40)
check("binding = risk", leaf["binding_constraints"] == ["risk"])
check("portfolio_pct = 20", leaf["portfolio_pct"] == 20.0)


# ── 3. Concentration-limited (opt-in 25%) ─────────────────────────────
print("\nconcentration cap binds (max_position_fraction=0.25):")
leaf = one(500.0, 498.0, max_position_fraction=0.25)  # conc = 10000*0.25/500 = 5
check("shares = 5 (concentration-limited)", leaf["shares"] == 5)
check("binding = concentration", leaf["binding_constraints"] == ["concentration"])
check("portfolio_pct = 25", leaf["portfolio_pct"] == 25.0)
check("planned_loss_at_stop = 5 × $2 = $10", leaf["planned_loss_at_stop"] == 10.0)


# ── 4. Invalid stop (>= entry) invalidates sizing, no capital-only ────
print("\nstop >= entry → sizing invalidated (not capital-only):")
leaf = one(500.0, 500.0)
check("shares is None", leaf["shares"] is None)
check("sizing_evaluated is False", leaf["sizing_evaluated"] is False)
check("binding_constraints empty", leaf["binding_constraints"] == [])
check("risk constraint evaluated=False", leaf["constraints"]["risk"]["evaluated"] is False)
check("capital still recorded (20) but not used", leaf["constraints"]["capital"]["shares"] == 20)
check("warns about stop", any("Stop must be below entry" in w for w in leaf["warnings"]))


# ── 5. Unit pinning ───────────────────────────────────────────────────
print("\nunit pinning (fraction vs percent):")
raised = False
try:
    one(500.0, 498.0, max_position_fraction=25)  # percent form → must reject
except ValueError:
    raised = True
check("max_position_fraction=25 raises ValueError", raised)
check("max_position_fraction=0.25 caps at 25%", one(500.0, 498.0, max_position_fraction=0.25)["portfolio_pct"] == 25.0)
check("risk_pct=2.0 still means 2% ($200 budget)", one(50.0, 45.0, risk_pct=2.0)["risk_budget"] == 200.0)


# ── 6. Tie → both caps in binding_constraints ─────────────────────────
print("\ntied caps → both listed:")
# leverage 1× → capital 20; max_position_fraction 1.0 → concentration 20; risk 100
leaf = one(500.0, 498.0, max_position_fraction=1.0)
check("shares = 20", leaf["shares"] == 20)
check("binding = [capital, concentration]", leaf["binding_constraints"] == ["capital", "concentration"])


# ── 7. ADV metric only with finite positive ADV ───────────────────────
print("\nADV metric presence:")
check("missing ADV → position_pct_of_adv None", one(50.0, 45.0)["position_pct_of_adv"] is None)
check("missing ADV → adv_metrics_evaluated False", one(50.0, 45.0)["adv_metrics_evaluated"] is False)
leaf = one(50.0, 45.0, avg_volume=1_000_000)  # 40 shares / 1e6 * 100
check("ADV present → pct from FINAL shares", leaf["position_pct_of_adv"] == 0.004)
check("ADV present → evaluated True", leaf["adv_metrics_evaluated"] is True)

# liquidity hard cap only when participation fraction is set
leaf = one(50.0, 45.0, avg_volume=100_000, max_adv_participation_fraction=0.0001)  # liq = 10
check("liquidity cap binds when configured", leaf["shares"] == 10 and "liquidity" in leaf["binding_constraints"])


# ── Summary ───────────────────────────────────────────────────────────
print(f"\n{'='*50}\n  {_passed} passed, {_failed} failed\n{'='*50}")
sys.exit(1 if _failed else 0)
