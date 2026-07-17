#!/usr/bin/env python3
"""
Tests for portfolio-review CSV parsing (bug #12 fix).

Covers both CSV branches (with header / without header) plus the shared
`_parse_number` helper, using the agreed case matrix:
    valid, $150.50, N/A, 1O0 (letter O), nan, inf, negative, zero,
    and a bad row sitting between two valid rows.

Run:  python tests/test_csv_parsing.py
"""
import os, sys, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from scripts.run_portfolio_review import _parse_number, load_holdings_from_file

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


def _write_csv(text):
    fd, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w") as f:
        f.write(text)
    return path


# ── 1. _parse_number unit behaviour ──────────────────────────────────
print("\n_parse_number:")
check("plain number", _parse_number("150.50") == 150.50)
check("dollar sign stripped", _parse_number("$150.50") == 150.50)
check("quoted thousands", _parse_number("485,000") == 485000.0)
check("None -> None", _parse_number(None) is None)
check("blank -> None", _parse_number("   ") is None)
check("N/A sentinel -> None", _parse_number("N/A") is None)
check("dash sentinel -> None", _parse_number("-") is None)
check("nan -> None (float accepts it)", _parse_number("nan") is None)
check("inf -> None (float accepts it)", _parse_number("inf") is None)

raised = False
try:
    _parse_number("1O0")  # letter O, genuinely malformed
except ValueError:
    raised = True
check("malformed '1O0' raises ValueError", raised)


# ── 2. CSV WITH header — bad row between valid rows ───────────────────
print("\nCSV with header (bad row between two valid rows):")
path = _write_csv(
    "ticker,shares,avg_cost\n"
    "AAPL,100,150.50\n"
    "BADD,100,$abc\n"        # malformed cost -> skip only this row
    "MSFT,50,380.00\n"
)
h = load_holdings_from_file(path)
os.unlink(path)
tickers = {x["ticker"] for x in h}
check("2 valid holdings kept", len(h) == 2)
check("AAPL kept", "AAPL" in tickers)
check("MSFT kept", "MSFT" in tickers)
check("BADD skipped (not crashed)", "BADD" not in tickers)


# ── 3. CSV WITHOUT header — full case matrix ──────────────────────────
print("\nCSV without header (case matrix):")
path = _write_csv(
    "AAPL,100,150.50\n"      # valid
    "TSLA,10,$250.00\n"      # dollar sign -> valid
    "NANX,5,nan\n"           # nan cost -> skip
    "INFX,5,inf\n"           # inf cost -> skip
    "NEGX,-5,100\n"          # negative shares -> skip
    "ZERX,0,100\n"           # zero shares -> skip
    "TYPO,1O0,150\n"         # letter O in shares -> skip
    "NVDA,25,500.00\n"       # valid (after the bad rows)
)
h = load_holdings_from_file(path)
os.unlink(path)
tickers = {x["ticker"] for x in h}
check("3 valid holdings kept (AAPL, TSLA, NVDA)", len(h) == 3)
check("dollar-sign row parsed", "TSLA" in tickers)
check("nan row skipped", "NANX" not in tickers)
check("inf row skipped", "INFX" not in tickers)
check("negative-shares row skipped", "NEGX" not in tickers)
check("zero-shares row skipped", "ZERX" not in tickers)
check("typo row skipped", "TYPO" not in tickers)
check("valid row after bad rows kept", "NVDA" in tickers)


# ── Summary ───────────────────────────────────────────────────────────
print(f"\n{'='*50}")
print(f"  {_passed} passed, {_failed} failed")
print(f"{'='*50}")
sys.exit(1 if _failed else 0)
