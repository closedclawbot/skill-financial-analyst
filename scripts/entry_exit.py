"""
Entry & Exit Calculator — 3 Entry Levels + 3 Sell Targets.

Uses a combination of technical indicators (S/R levels, Fibonacci, ATR,
Bollinger Bands, pivot points) to compute risk-defined entry and exit zones.

Entry Levels (buying zones):
    1. Aggressive  — closest to current price (for momentum plays)
    2. Moderate    — mid-range pullback target
    3. Conservative — deep pullback / strong support level

Exit Targets (selling zones):
    1. Target 1 — short-term (+1 ATR or nearest resistance)
    2. Target 2 — medium-term (Fibonacci extension or key resistance)
    3. Target 3 — stretch goal (major resistance / extension)

Also computes:
    - Stop loss suggestion
    - Risk/reward ratio for each entry→target pair
    - Position size suggestion (based on account risk %)

Usage:
    from scripts.entry_exit import compute_entry_exit

    levels = compute_entry_exit(
        current_price=175.50,
        technicals=ta_data,  # from compute_technicals()
        score=7.2,           # composite score
    )
"""
import os, sys, math

_project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


def compute_entry_exit(current_price, technicals=None, score=5.0, risk_pct=2.0,
                       leverage_multiplier=1.0, max_position_fraction=None,
                       max_adv_participation_fraction=None):
    """
    Compute 3 entry levels, 3 exit targets, and stop loss.

    Args:
        current_price: Current stock price
        technicals: Dict from compute_technicals() containing S/R, Fibonacci,
                    pivot points, ATR, Bollinger Bands
        score: Composite score (0-10) — higher score = tighter entries
        risk_pct: Max portfolio risk per trade (default 2%)

    Returns:
        dict with entries, targets, stop_loss, risk_reward ratios
    """
    if current_price <= 0:
        raise ValueError("Current price must be positive")

    ta = technicals or {}
    atr = ta.get("atr_14") or current_price * 0.02  # fallback: 2% of price

    # Gather all available price levels
    supports = _get_supports(ta, current_price)
    resistances = _get_resistances(ta, current_price)
    fib = ta.get("fibonacci", {})
    pivots = ta.get("pivot_points", {})
    bb_lower = ta.get("bb_lower")
    bb_upper = ta.get("bb_upper")

    # ─── ENTRY LEVELS ────────────────────────────────────────────
    entries = _compute_entries(current_price, atr, supports, fib, pivots, bb_lower, score)

    # ─── EXIT TARGETS ────────────────────────────────────────────
    targets = _compute_targets(current_price, atr, resistances, fib, pivots, bb_upper, score)

    # ─── STOP LOSS ───────────────────────────────────────────────
    stop_loss = _compute_stop_loss(current_price, atr, supports, entries)

    # ─── RISK/REWARD ─────────────────────────────────────────────
    risk_reward = _compute_risk_reward(entries, targets, stop_loss)

    # ─── POSITION SIZING ─────────────────────────────────────────
    position_sizes = _compute_position_sizes(
        entries, stop_loss, risk_pct,
        avg_volume=ta.get("volume_avg_20"),
        leverage_multiplier=leverage_multiplier,
        max_position_fraction=max_position_fraction,
        max_adv_participation_fraction=max_adv_participation_fraction,
    )

    return {
        "current_price": current_price,
        "atr": round(atr, 2),
        "entries": {
            "aggressive": round(entries[0], 2),
            "moderate": round(entries[1], 2),
            "conservative": round(entries[2], 2),
        },
        "targets": {
            "target_1": round(targets[0], 2),
            "target_2": round(targets[1], 2),
            "target_3": round(targets[2], 2),
        },
        "stop_loss": round(stop_loss, 2),
        "risk_reward": risk_reward,
        "position_sizes": position_sizes,
        "context": {
            "supports_used": [round(s, 2) for s in supports[:5]],
            "resistances_used": [round(r, 2) for r in resistances[:5]],
            "fibonacci": {k: round(v, 2) for k, v in fib.get("retracements", {}).items()} if fib else {},
            "pivot": pivots.get("pivot"),
        },
    }


# ─── ENTRY COMPUTATION ─────────────────────────────────────────

def _compute_entries(current_price, atr, supports, fib, pivots, bb_lower, score):
    """
    Compute 3 entry levels below current price.

    Strategy:
    - Aggressive: small pullback (0.25-0.5 ATR below current, or nearest support)
    - Moderate: meaningful pullback (0.75-1.5 ATR, or Fib 23.6%/38.2%)
    - Conservative: deep pullback (2+ ATR, or Fib 50%/61.8%, or strong support)

    Higher scores = smaller pullback required (more conviction)
    """
    # Score-adjusted ATR multipliers (higher score = tighter entries)
    aggr_mult = max(0.15, 0.50 - (score - 5) * 0.04)   # 0.50 at score 5, 0.30 at 10
    mod_mult = max(0.50, 1.25 - (score - 5) * 0.08)     # 1.25 at score 5, 0.85 at 10
    cons_mult = max(1.0, 2.25 - (score - 5) * 0.12)     # 2.25 at score 5, 1.65 at 10

    # Start with ATR-based entries
    e_aggr = current_price - atr * aggr_mult
    e_mod = current_price - atr * mod_mult
    e_cons = current_price - atr * cons_mult

    # Refine with support levels if available
    if supports:
        # Aggressive: snap to nearest support if it's within 1 ATR
        near_supports = [s for s in supports if current_price - atr * 1.5 < s < current_price]
        if near_supports:
            e_aggr = max(e_aggr, near_supports[0])  # use higher of the two

        # Conservative: snap to deeper support
        deep_supports = [s for s in supports if s < current_price - atr]
        if deep_supports:
            e_cons = min(e_cons, deep_supports[0])

    # Refine with Fibonacci levels
    retracements = fib.get("retracements", {})
    if retracements:
        fib_levels = sorted(retracements.values(), reverse=True)
        fib_below = [f for f in fib_levels if f < current_price]
        if len(fib_below) >= 1:
            # Use Fib levels as guides
            fib_near = fib_below[0]
            if abs(fib_near - e_mod) / current_price < 0.03:
                e_mod = fib_near  # snap to Fibonacci if close
        if len(fib_below) >= 3:
            fib_deep = fib_below[2]
            if abs(fib_deep - e_cons) / current_price < 0.05:
                e_cons = fib_deep

    # Refine with pivot points
    if pivots:
        s1 = pivots.get("s1", 0)
        s2 = pivots.get("s2", 0)
        if s1 and abs(s1 - e_mod) / current_price < 0.02:
            e_mod = s1
        if s2 and abs(s2 - e_cons) / current_price < 0.03:
            e_cons = s2

    # Refine with Bollinger lower band
    if bb_lower and bb_lower < current_price:
        if abs(bb_lower - e_cons) / current_price < 0.03:
            e_cons = bb_lower

    # Ensure entries are in descending order and all below current price
    e_aggr = min(e_aggr, current_price * 0.995)   # at least 0.5% below
    e_cons = min(e_cons, e_mod - atr * 0.25)       # at least 0.25 ATR apart
    e_mod = min(e_mod, e_aggr - atr * 0.15)        # keep spacing

    # Final ordering: aggressive > moderate > conservative
    entries = sorted([e_aggr, e_mod, e_cons], reverse=True)

    return entries


# ─── TARGET COMPUTATION ─────────────────────────────────────────

def _compute_targets(current_price, atr, resistances, fib, pivots, bb_upper, score):
    """
    Compute 3 exit targets above current price.

    Strategy:
    - Target 1: 1-1.5 ATR above current, or nearest resistance
    - Target 2: 2-3 ATR, or Fibonacci extension (127.2%), or R2
    - Target 3: 4+ ATR, or Fibonacci extension (161.8%/200%), or R3

    Higher scores = more ambitious targets (more conviction in upside)
    """
    t1_mult = 1.0 + (score - 5) * 0.10     # 1.0 at score 5, 1.5 at 10
    t2_mult = 2.5 + (score - 5) * 0.15     # 2.5 at score 5, 3.25 at 10
    t3_mult = 4.0 + (score - 5) * 0.25     # 4.0 at score 5, 5.25 at 10

    t1 = current_price + atr * t1_mult
    t2 = current_price + atr * t2_mult
    t3 = current_price + atr * t3_mult

    # Refine with resistance levels
    if resistances:
        near_resist = [r for r in resistances if r > current_price]
        if near_resist:
            if abs(near_resist[0] - t1) / current_price < 0.03:
                t1 = near_resist[0]
            if len(near_resist) >= 2 and abs(near_resist[1] - t2) / current_price < 0.05:
                t2 = near_resist[1]

    # Refine with Fibonacci extensions
    extensions = fib.get("extensions", {})
    if extensions:
        ext_values = sorted(extensions.values())
        ext_above = [e for e in ext_values if e > current_price]
        if ext_above:
            if abs(ext_above[0] - t2) / current_price < 0.05:
                t2 = ext_above[0]
            if len(ext_above) >= 2 and abs(ext_above[1] - t3) / current_price < 0.08:
                t3 = ext_above[1]

    # Refine with pivot points
    if pivots:
        r1 = pivots.get("r1", 0)
        r2 = pivots.get("r2", 0)
        r3 = pivots.get("r3", 0)
        if r1 and abs(r1 - t1) / current_price < 0.02:
            t1 = r1
        if r2 and abs(r2 - t2) / current_price < 0.04:
            t2 = r2
        if r3 and abs(r3 - t3) / current_price < 0.06:
            t3 = r3

    # Refine with Bollinger upper band
    if bb_upper and bb_upper > current_price:
        if abs(bb_upper - t1) / current_price < 0.02:
            t1 = bb_upper

    # Ensure targets are in ascending order and above current price
    t1 = max(t1, current_price * 1.01)     # at least 1% above
    t2 = max(t2, t1 + atr * 0.5)           # spacing
    t3 = max(t3, t2 + atr * 0.5)

    targets = sorted([t1, t2, t3])

    return targets


# ─── STOP LOSS ──────────────────────────────────────────────────

def _compute_stop_loss(current_price, atr, supports, entries):
    """
    Compute stop loss below the conservative entry.

    Uses the furthest support below conservative entry, or 1.5-2 ATR below it.
    """
    conservative_entry = entries[-1] if entries else current_price * 0.95

    # Default: 1.5 ATR below conservative entry
    stop = conservative_entry - atr * 1.5

    # If there's a support just below conservative entry, use it with a buffer
    deep_supports = [s for s in supports if s < conservative_entry - atr * 0.25]
    if deep_supports:
        # Place stop just below the support (with ATR buffer)
        stop = min(stop, deep_supports[0] - atr * 0.25)

    # Never more than 8% below current price (risk cap)
    stop = max(stop, current_price * 0.92)

    # CRITICAL: ensure stop is at least 1 ATR below the conservative entry
    # to avoid near-zero risk denominators that produce absurd R:R ratios
    max_stop = conservative_entry - atr * 1.0
    if stop > max_stop:
        stop = max_stop

    return stop


# ─── RISK/REWARD RATIOS ────────────────────────────────────────

def _compute_risk_reward(entries, targets, stop_loss):
    """Compute R:R ratio for each entry→target combination."""
    ratios = {}
    entry_names = ["aggressive", "moderate", "conservative"]
    target_names = ["target_1", "target_2", "target_3"]

    for i, (e_name, entry) in enumerate(zip(entry_names, entries)):
        for j, (t_name, target) in enumerate(zip(target_names, targets)):
            risk = entry - stop_loss
            reward = target - entry
            if risk > 0:
                rr = round(min(reward / risk, 20.0), 2)  # cap at 20x
            else:
                rr = 0
            ratios[f"{e_name}→{t_name}"] = {
                "entry": round(entry, 2),
                "target": round(target, 2),
                "stop": round(stop_loss, 2),
                "risk": round(risk, 2),
                "reward": round(reward, 2),
                "rr_ratio": rr,
                "favorable": 2.0 <= rr <= 15.0,  # >15x is likely unrealistic
            }

    return ratios


# ─── POSITION SIZING ───────────────────────────────────────────

_SIZING_NOTE = ("Illustrative standalone-account scenario — existing holdings, "
                "open orders and available cash are NOT considered.")


def _compute_position_sizes(entries, stop_loss, risk_pct=2.0, avg_volume=None,
                            leverage_multiplier=1.0, max_position_fraction=None,
                            max_adv_participation_fraction=None,
                            account_sizes=(10_000, 50_000, 100_000)):
    """
    Suggest position sizes as ``min`` of several constraints, per illustrative
    account scenario. NOT a portfolio-aware sizer (see _SIZING_NOTE).

    Units — pinned explicitly to avoid the fraction/percent trap:
      - ``risk_pct``: PERCENT points (legacy API), 2.0 == 2%.
      - ``max_position_fraction`` / ``max_adv_participation_fraction``: FRACTIONS
        in (0, 1]  (0.25 == 25%). Passing 25 raises ValueError.
      - ``leverage_multiplier``: 1.0 == cash (no leverage). Margin only if the
        caller explicitly passes > 1.
    Output ``*_pct`` fields are human percents (25.0, 0.4).

    Constraints:
      - risk, capital  → MANDATORY. If either can't be evaluated (e.g. a
        long-position stop that is not below entry), sizing for that
        entry/account is invalidated (shares=None) rather than emitting a
        capital-only number that looks authoritative.
      - concentration, liquidity → OPTIONAL (off unless configured).
    """
    if not (isinstance(risk_pct, (int, float)) and risk_pct > 0 and math.isfinite(risk_pct)):
        raise ValueError("risk_pct must be a positive number (percent points, e.g. 2.0)")
    if not (isinstance(leverage_multiplier, (int, float)) and leverage_multiplier > 0
            and math.isfinite(leverage_multiplier)):
        raise ValueError("leverage_multiplier must be > 0 (1.0 = cash)")
    if max_position_fraction is not None and not (0 < max_position_fraction <= 1.0):
        raise ValueError("max_position_fraction must be a FRACTION in (0, 1] (0.25 for 25%), not a percent")
    if max_adv_participation_fraction is not None and not (0 < max_adv_participation_fraction <= 1.0):
        raise ValueError("max_adv_participation_fraction must be a FRACTION in (0, 1]")

    risk_fraction = risk_pct / 100.0
    adv = avg_volume if (isinstance(avg_volume, (int, float)) and math.isfinite(avg_volume)
                         and avg_volume > 0) else None

    entry_names = ["aggressive", "moderate", "conservative"]
    sizes = {}
    for e_name, entry in zip(entry_names, entries):
        entry_sizes = {}
        for acct in account_sizes:
            entry_sizes[f"${acct:,}"] = _size_one(
                entry, stop_loss, acct, risk_fraction, adv,
                leverage_multiplier, max_position_fraction, max_adv_participation_fraction)
        sizes[e_name] = entry_sizes
    return sizes


def _size_one(entry, stop_loss, account, risk_fraction, adv,
              leverage_multiplier, max_position_fraction, max_adv_participation_fraction):
    """Size a single (entry, account) cell. Returns the rich leaf dict."""
    constraints = {}
    warnings = []
    risk_budget = round(account * risk_fraction, 2)

    # ── risk (MANDATORY) ──
    risk_per_share = entry - stop_loss
    if risk_per_share > 0:
        constraints["risk"] = {"shares": int(risk_budget / risk_per_share), "evaluated": True}
    else:
        constraints["risk"] = {"shares": None, "evaluated": False}
        warnings.append("Stop must be below entry for long-position sizing.")

    # ── capital (MANDATORY) ──
    if entry > 0:
        constraints["capital"] = {"shares": int(account * leverage_multiplier / entry), "evaluated": True}
    else:
        constraints["capital"] = {"shares": None, "evaluated": False}
        warnings.append("Entry price must be positive.")

    # ── concentration (OPTIONAL) ──
    if max_position_fraction is not None and entry > 0:
        constraints["concentration"] = {"shares": int(account * max_position_fraction / entry), "evaluated": True}
    else:
        constraints["concentration"] = {"shares": None, "evaluated": False}

    # ── liquidity (OPTIONAL — hard cap only if a participation fraction is set) ──
    if max_adv_participation_fraction is not None and adv is not None:
        constraints["liquidity"] = {"shares": int(max_adv_participation_fraction * adv), "evaluated": True}
    else:
        constraints["liquidity"] = {"shares": None, "evaluated": False}

    base = {
        "constraints": constraints,
        "risk_budget": risk_budget,
        "warnings": warnings,
        "note": _SIZING_NOTE,
    }

    # A mandatory constraint that couldn't be evaluated invalidates the cell.
    if not (constraints["risk"]["evaluated"] and constraints["capital"]["evaluated"]):
        return {**base, "shares": None, "sizing_evaluated": False, "binding_constraints": [],
                "notional": None, "portfolio_pct": None, "planned_loss_at_stop": None,
                "position_pct_of_adv": None, "adv_metrics_evaluated": False}

    evaluated = {k: v["shares"] for k, v in constraints.items()
                 if v["evaluated"] and v["shares"] is not None}
    final_shares = min(evaluated.values())
    binding = sorted(k for k, s in evaluated.items() if s == final_shares)

    if final_shares <= 0:
        warnings.append("Insufficient capital for one whole share.")

    notional = round(final_shares * entry, 2)
    # ADV participation is computed from the FINAL (post-cap) share count.
    if adv is not None:
        position_pct_of_adv, adv_eval = round(final_shares / adv * 100, 4), True
    else:
        position_pct_of_adv, adv_eval = None, False

    return {
        **base,
        "shares": final_shares,
        "sizing_evaluated": True,
        "binding_constraints": binding,
        "notional": notional,
        "portfolio_pct": round(notional / account * 100, 1) if account else None,
        "planned_loss_at_stop": round(final_shares * risk_per_share, 2),
        "position_pct_of_adv": position_pct_of_adv,
        "adv_metrics_evaluated": adv_eval,
    }


# ─── HELPERS ────────────────────────────────────────────────────

def _get_supports(ta, current_price):
    """Extract all support levels below current price, sorted closest first."""
    levels = []

    # From S/R computation
    sr = ta.get("support_resistance", {})
    levels.extend(sr.get("supports", []))

    # From pivot points
    pivots = ta.get("pivot_points", {})
    for key in ("s1", "s2", "s3"):
        val = pivots.get(key)
        if val and val > 0:
            levels.append(val)

    # From Fibonacci retracements
    fib = ta.get("fibonacci", {})
    for level_price in fib.get("retracements", {}).values():
        if level_price < current_price:
            levels.append(level_price)

    # SMA levels as dynamic support
    for sma_key in ("sma_50", "sma_200", "ema_50"):
        val = ta.get(sma_key)
        if val and val < current_price:
            levels.append(val)

    # Deduplicate and sort (closest to price first)
    levels = sorted(set(l for l in levels if l > 0 and l < current_price), reverse=True)
    return levels


def _get_resistances(ta, current_price):
    """Extract all resistance levels above current price, sorted closest first."""
    levels = []

    sr = ta.get("support_resistance", {})
    levels.extend(sr.get("resistances", []))

    pivots = ta.get("pivot_points", {})
    for key in ("r1", "r2", "r3"):
        val = pivots.get(key)
        if val and val > 0:
            levels.append(val)

    fib = ta.get("fibonacci", {})
    for level_price in fib.get("extensions", {}).values():
        if level_price > current_price:
            levels.append(level_price)

    for sma_key in ("sma_50", "sma_200", "ema_50"):
        val = ta.get(sma_key)
        if val and val > current_price:
            levels.append(val)

    levels = sorted(set(l for l in levels if l > current_price))
    return levels


# ─── FORMATTED OUTPUT ───────────────────────────────────────────

def format_entry_exit(result, ticker=""):
    """Format entry/exit levels as a readable string for reports."""
    lines = []
    prefix = f"[{ticker}] " if ticker else ""

    lines.append(f"{prefix}ENTRY & EXIT LEVELS")
    lines.append("=" * 60)
    lines.append(f"  Current Price:  ${result['current_price']:.2f}")
    lines.append(f"  ATR (14):       ${result['atr']:.2f}")
    lines.append("")

    lines.append("  ENTRY ZONES (Buy)")
    lines.append("  " + "-" * 50)
    e = result["entries"]
    lines.append(f"    Aggressive:    ${e['aggressive']:.2f}  (closest to market)")
    lines.append(f"    Moderate:      ${e['moderate']:.2f}")
    lines.append(f"    Conservative:  ${e['conservative']:.2f}  (deepest pullback)")
    lines.append("")

    lines.append("  EXIT TARGETS (Sell)")
    lines.append("  " + "-" * 50)
    t = result["targets"]
    lines.append(f"    Target 1:      ${t['target_1']:.2f}  (short-term)")
    lines.append(f"    Target 2:      ${t['target_2']:.2f}  (medium-term)")
    lines.append(f"    Target 3:      ${t['target_3']:.2f}  (stretch goal)")
    lines.append("")

    lines.append(f"  STOP LOSS:       ${result['stop_loss']:.2f}")
    lines.append("")

    # Best risk/reward combos
    lines.append("  RISK / REWARD")
    lines.append("  " + "-" * 50)
    rr = result["risk_reward"]
    best = sorted(rr.items(), key=lambda x: -x[1]["rr_ratio"])[:3]
    for name, data in best:
        marker = " ***" if data["favorable"] else ""
        lines.append(f"    {name:<30} R:R = {data['rr_ratio']:.1f}x{marker}")

    return "\n".join(lines)
