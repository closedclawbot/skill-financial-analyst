#!/usr/bin/env python3
"""
Tests for the cached-.md markdown formatter (bug #13 fix).

Drives the REAL producers (compute_technicals, compute_entry_exit) and feeds
their output into _format_markdown() exactly as run_deep_dive does, then
asserts the formatted report no longer shows "N/A" for data that was actually
computed. Using real producer output (not a hand-built ideal dict) means this
test also catches future display-schema drift.

Run:  .venv/bin/python tests/test_markdown_formatter.py
"""
import os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from scripts.technical_analysis import compute_technicals
from scripts.entry_exit import compute_entry_exit
from scripts.data_cache import _format_markdown

_passed = 0
_failed = 0


def check(name, cond):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  ✓ PASS  {name}")
    else:
        _failed += 1
        print(f"  ✗ FAIL  {name}")


def _make_df(n):
    """Deterministic synthetic OHLCV with a mild uptrend + wobble."""
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    rng = np.random.RandomState(42)
    base = np.linspace(100, 150, n) + np.sin(np.linspace(0, 25, n)) * 4
    close = pd.Series(base, index=idx)
    high = close + 1.5
    low = close - 1.5
    open_ = close.shift(1).fillna(close.iloc[0])
    vol = pd.Series(rng.randint(1_000_000, 5_000_000, n), index=idx)
    return pd.DataFrame({"Open": open_, "High": high, "Low": low,
                         "Close": close, "Volume": vol})


# ── 1. Full history (260 rows) — everything should populate ───────────
print("\nTechnicals + Price + Entry/Exit (260 rows, full history):")
df = _make_df(260)
tech = compute_technicals(df, "TEST")
price = {
    "ticker": "TEST", "period": "1y", "interval": "1d", "data": df,
    "latest_close": float(df["Close"].iloc[-1]),
    "latest_volume": int(df["Volume"].iloc[-1]), "records": len(df),
}
ee = compute_entry_exit(price["latest_close"], tech, score=7.0)
data = {
    "price_history": price,
    "technicals": tech,
    "entry_exit": ee,
    "fundamentals": {"52w_high": float(df["High"].max()),
                     "52w_low": float(df["Low"].min())},
}
md = _format_markdown("TEST", "2026-07-17", data)

# Sanity: producers actually emitted these (so N/A would be a formatter bug)
check("producer emitted rsi_14", tech.get("rsi_14") is not None)
check("producer emitted macd_line", tech.get("macd_line") is not None)
check("producer emitted support_resistance", bool(tech.get("support_resistance")))

# Technicals no longer N/A
check("RSI not N/A", "RSI (14): N/A" not in md)
check("MACD not N/A", "- MACD: N/A" not in md)
check("MACD Histogram not N/A", "MACD Histogram: N/A" not in md)
check("ATR not N/A", "ATR (14): N/A" not in md)
check("Bollinger Middle not N/A", "Bollinger Middle: N/A" not in md)
check("BB %B not N/A", "BB %B (0-1): N/A" not in md)
check("Supports rendered", "- Supports:" in md)
check("Fibonacci section rendered", "### Fibonacci Levels" in md)
check("raw Technical JSON safety net present", "### All Technical Data" in md)
check("volume_trend line removed", "Volume Trend" not in md)

# Price header no longer N/A
check("Volume not N/A", "**Volume:** N/A" not in md)
check("Previous Close not N/A", "**Previous Close:** $N/A" not in md)
check("52-Week High not N/A", "**52-Week High:** $N/A" not in md)
check("Daily Change rendered", "Daily Change:" in md)

# Entry/Exit R:R now rendered (was never shown — read from wrong place)
check("Risk/Reward section rendered", "### Risk / Reward" in md)
check("R:R ratio value shown", "R:R =" in md)

# above_sma with full history is a real bool -> Above/Below (not N/A)
check("SMA200 trend is Above/Below (bool)",
      ("Price vs SMA200: Above" in md) or ("Price vs SMA200: Below" in md))


# ── 2. Short history (60 rows) — SMA200 unknown -> must show N/A ──────
print("\nShort history (60 rows) — above_sma200 is None:")
df2 = _make_df(60)
tech2 = compute_technicals(df2, "SHRT")
check("producer: above_sma200 is None (no 200 bars)", tech2.get("above_sma200") is None)
data2 = {"technicals": tech2}
md2 = _format_markdown("SHRT", "2026-07-17", data2)
check("SMA200 shows N/A, not a false 'Below'", "Price vs SMA200: N/A" in md2)
check("SMA200 not falsely 'Below'", "Price vs SMA200: Below" not in md2)


# ── Summary ───────────────────────────────────────────────────────────
print(f"\n{'='*50}")
print(f"  {_passed} passed, {_failed} failed")
print(f"{'='*50}")
sys.exit(1 if _failed else 0)
