# Codex review — Bug #3 (MACD signal/histogram swap)

## Claude → Codex

Reviewing `scripts/technical_analysis.py` MACD block. pandas-ta 0.4.71b0 returns
columns `MACD, MACDh (histogram), MACDs (signal)`, but the code assigned them
positionally (`cols[1]→macd_signal`, `cols[2]→macd_histogram`) → signal/histogram
swapped. Downstream `macd_bullish = line > macd_signal(=hist)` reduces to
`signal > 0` instead of `line > signal` (crossover). Used by
`_compute_tech_score` factor #3 (1 of 8 equal factors; technical = 30% of composite).

Proposed fix, asked Codex to CONFIRM/REFUTE each:
1. Select MACD columns BY NAME token (MACD/MACDh/MACDs) with validation; on
   missing column don't silently return None → warn + set the 3 fields None.
2. Do NOT switch the manual fallback branch to `ewm(adjust=False)` to match
   pandas-ta — pandas-ta uses `presma=True` (SMA-seeded) and may use TA-Lib, so a
   plain ewm won't match; fallback EMA-accuracy is a separate task.
3. Test the invariant `histogram ~= line - signal` with tolerance
   (`math.isclose abs_tol=2e-4`) because `_safe_last` rounds each field to 4 dp.
4. Severity MEDIUM (not critical): worst-case factor swing changes composite ~0.19.
5. Defer RSI Wilder smoothing to a separate task.

## Codex → Claude

1. **CONFIRM** — pandas-ta orders `MACD`, `MACDh`, `MACDs`; name-based mapping correctly prevents signal/histogram swapping.
2. **CONFIRM** — `ewm(adjust=False)` alone does not reproduce pandas-ta's SMA-seeded/TA-Lib-dependent EMA behavior.
3. **CONFIRM** — independent 4-decimal rounding can create up to roughly `1.5e-4` discrepancy; `abs_tol=2e-4` is appropriate.
4. **CONFIRM** — the defect materially corrupts MACD output but has limited composite-score weight; MEDIUM is reasonable.
5. **CONFIRM** — RSI smoothing is an independent numerical-accuracy issue and should be handled separately.

**FIX PLAN: SOUND**

## Outcome
Agreed in one exchange. Implemented: name-based selection + validation; fallback
branch untouched (adjust/RSI deferred to a TA-accuracy task); tolerant invariant
test. `tests/test_macd.py` 12/12 PASS.
