# Codex review — Bugs #1 / #2 (ROE / Debt-to-Equity units)

## Claude → Codex

`scripts/scoring.py` `_score_fundamental()` used magnitude heuristics:
`roe*100 if abs(roe)<1 else roe`; `de/100 if de>10 else de`; growth/margin `<5`/`<1`.

Live yfinance `.info` (2026-07): `returnOnEquity` NVDA 1.14 / AAPL 1.41 / KO 0.43
(a FRACTION); `debtToEquity` KO 124.9 / AAPL 79.5 / NVDA 6.555 (PERCENT of ratio,
79.5 = 0.795x); growth/margins fractions; `dividendYield` 0.32 (AAPL) already
percent (0.32%).

So heuristics misfire: NVDA ROE 1.14 → kept → ~1% (score 4); NVDA D/E 6.555 → not
>10 → ratio 6.555 → "extremely leveraged" (score 2) though true ratio 0.066.

Fix implemented: explicit converters, no magnitude guessing —
`_pct(frac)=frac*100` (ROE/growth/margins), `_de_ratio(de)=de/100` (D/E).
Behavior-preserving for normal names; only mis-scored edges change.

Scope (kept separate — asked Codex to sanity-check): `dividendYield` is the
OPPOSITE case (already percent → must NOT *100) = bug #14 in `data_cache._fmt_pct`,
separate; `finnhub_financials`/`fmp_fundamentals` emit their own units and aren't
normalized to these keys (separate task), so `_score_fundamental` only ever sees
yfinance-keyed data today.

Asked: (A) unit map correct? (B) converters correct & behavior-preserving?
(C) right to fix scoring to yfinance now and defer #14 + finnhub/fmp normalization?

## Codex → Claude

- **A — Confirm.** Unit map matches the stated 2026 yfinance `.info` values: ROE/growth/margins are fractions; D/E is percentage-of-ratio; dividend yield is already percent.
- **B — Confirm.** `_pct(x)=x*100` and `_de_ratio(x)=x/100` are correct. They preserve ordinary cases previously handled correctly and fix ROE ≥100% and D/E ≤10%. Minor caveat: behavior also changes for unusual negative D/E and extreme inputs — appropriate under the explicit schema.
- **C — Confirm.** Fix scoring to the only schema it currently consumes; defer dividend display and fallback-provider normalization as separate concerns.

**Only flaw/risk:** this remains correct only while `_score_fundamental()` receives yfinance-schema fields. Add tests and ideally document/assert that boundary to prevent future Finnhub/FMP data from being silently mis-scaled.

## Outcome
Agreed in one exchange. Codex's boundary note addressed: yfinance convention is
documented in the `_pct`/`_de_ratio` docstrings, and `tests/test_fundamental_units.py`
(18/18 PASS) pins the behavior with real yfinance values.
