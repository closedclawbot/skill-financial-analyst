#!/usr/bin/env python3
"""
Tests for edge-value display (#22) and the dead Finnhub news link (#23).

#22a  FCF was `f"${fcf_b:.2f}B"` → a small negative rendered "$-0.00B" (sign
      inside '$', magnitude rounded away). Now `_fmt_money` → "-$5.00M".
#22b  A tiny-negative profit margin rounded to "0.0%" while the note said
      "Negative margins — losing money". The console/portfolio printers apply
      `f"{value:.1f}%"` ONLY to floats, so scoring now emits a pre-formatted
      adaptive string ("-0.03%") for that edge — this test replicates the exact
      printer branch to prove the FINAL display, not just the scoring dict.
#23   Finnhub free-tier news `url` (finnhub.io/api/news?id=...) 302s to the
      homepage — a dead link. `_is_finnhub_redirect` detects it (exact host +
      /api/news path); it's blanked at the source and defensively in the
      collector. AV `url` / RSS `link` must stay untouched.

Run:  python3 tests/test_display_and_news.py   (no deps, no network)
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from scripts.scoring import _score_fundamental, _fmt_money
from scripts.data_fetchers import _is_finnhub_redirect
from scripts.run_deep_dive import _collect_articles

_passed = _failed = 0


def check(name, cond):
    global _passed, _failed
    _passed += 1 if cond else 0
    _failed += 0 if cond else 1
    print(f"  {'✓ PASS' if cond else '✗ FAIL'}  {name}")


def factor(fund, key):
    return _score_fundamental(fund)["factor_details"][key]


def render(key, f_data):
    """Mirror the EXACT factor-value formatting both printers use
    (run_deep_dive.py:679-692, run_portfolio_review.py:625-637): `.1f%` is
    applied only to FLOAT values of these keys; everything else prints verbatim."""
    value = f_data.get("value", "N/A")
    if isinstance(value, float):
        if key in ("revenue_growth", "eps_growth", "profit_margin", "roe"):
            value = f"{value:.1f}%"
    elif value is None:
        value = "—"
    return str(value)


# ── #22a — _fmt_money: sign outside '$', adaptive scale ────────────────
print("\n#22a _fmt_money (FCF):")
check("-$5M → '-$5.00M' (not '$-0.00B')", _fmt_money(-5e6) == "-$5.00M")
check("+$12.3B → '$12.30B'", _fmt_money(12.3e9) == "$12.30B")
check("-$5K → '-$5.00K'", _fmt_money(-5e3) == "-$5.00K")
check("+$500 (sub-K) → '$500'", _fmt_money(500) == "$500")
check("0 → '$0'", _fmt_money(0) == "$0")
check("None → None", _fmt_money(None) is None)
# end-to-end through the printer: FCF value is a string → printed verbatim
check("FCF -5M renders '-$5.00M' via printer",
      render("free_cash_flow", factor({"free_cash_flow": -5e6}, "free_cash_flow")) == "-$5.00M")
check("FCF never shows '$-0.00B'",
      "$-0.00B" != render("free_cash_flow", factor({"free_cash_flow": -5e6}, "free_cash_flow")))


# ── #22b — profit margin near-zero: display matches the 'negative' note ─
print("\n#22b profit margin (final printer display):")
tiny_neg = render("profit_margin", factor({"profit_margin": -0.0003}, "profit_margin"))  # -0.03%
check("tiny negative margin renders '-0.03%' (not '0.0%')", tiny_neg == "-0.03%")
check("tiny negative margin is NOT '0.0%'", tiny_neg not in ("0.0%", "-0.0%"))
check("tiny negative margin carries the minus sign", tiny_neg.startswith("-"))
# behavior preserved: normal margins still go through the float .1f path
check("normal -30% margin → '-30.0%' (unchanged)",
      render("profit_margin", factor({"profit_margin": -0.30}, "profit_margin")) == "-30.0%")
check("normal +12% margin → '12.0%' (unchanged)",
      render("profit_margin", factor({"profit_margin": 0.12}, "profit_margin")) == "12.0%")
# a value that rounds to a NONZERO 1-decimal must NOT take the string path
check("margin -0.06% → '-0.1%' (rounds to nonzero, stays float path)",
      render("profit_margin", factor({"profit_margin": -0.0006}, "profit_margin")) == "-0.1%")
# NOTE (out of #22/#23 scope): `margin = profit_margin or operating_margin` treats a
# genuine 0.0 as falsy → no-data "—". Pre-existing quirk, documented not fixed here.
check("genuine 0.0 margin → '—' (pre-existing `or` no-data quirk, documented)",
      render("profit_margin", factor({"profit_margin": 0.0}, "profit_margin")) == "—")


# ── #23 — _is_finnhub_redirect: exact host + path ─────────────────────
print("\n#23 _is_finnhub_redirect:")
check("finnhub /api/news → True",
      _is_finnhub_redirect("https://finnhub.io/api/news?id=abc123") is True)
check("real source article → False",
      _is_finnhub_redirect("https://www.benzinga.com/news/boxabl-spac") is False)
check("empty / None → False", _is_finnhub_redirect("") is False and _is_finnhub_redirect(None) is False)
check("look-alike host (finnhub.io.evil.com) → False",
      _is_finnhub_redirect("https://finnhub.io.evil.com/api/news?id=x") is False)
check("finnhub but different path → False",
      _is_finnhub_redirect("https://finnhub.io/quote/AAPL") is False)


# ── #23 — _collect_articles: drop finnhub link, keep AV/RSS ────────────
print("\n#23 _collect_articles (drop dead finnhub link, preserve AV/RSS):")
# cached path: old cache still carries the redirect url → defensive filter drops it
fh_news_cached = {"articles": [
    {"headline": "Top movers after hours", "source": "ChartMill",
     "url": "https://finnhub.io/api/news?id=deadbeef", "datetime": 1700000000},
]}  # no sentiment_scores → finnhub branch
arts = _collect_articles("FGMC", fh_news_cached, [])
fh = [a for a in arts if a["source"] == "ChartMill"][0]
check("cached finnhub redirect link dropped → ''", fh["link"] == "")
check("finnhub article title/source preserved", fh["title"] == "Top movers after hours")

# new path: source already blanked url → stays ''
fh_news_new = {"articles": [
    {"headline": "BOXABL completes merger", "source": "Benzinga", "url": "", "datetime": 1700000001},
]}
arts2 = _collect_articles("FGMC", fh_news_new, [])
check("source-blanked finnhub link stays ''",
      [a for a in arts2 if a["source"] == "Benzinga"][0]["link"] == "")

# AV path untouched (has sentiment_scores → AV branch; real url preserved)
av_news = {"articles": [{"title": "AAPL rallies", "source": "Reuters",
                         "url": "https://reuters.com/aapl", "time_published": "20260718T120000",
                         "ticker_sentiment": []}],
           "sentiment_scores": [0.2]}
arts3 = _collect_articles("AAPL", av_news, [])
check("AV real url preserved (untouched)",
      [a for a in arts3 if a["source"] == "Reuters"][0]["link"] == "https://reuters.com/aapl")

# RSS path untouched
rss = [{"title": "SA thesis on KO", "source": "Seeking Alpha",
        "link": "https://seekingalpha.com/article/ko", "summary": "", "published": "", "sentiment": None}]
arts4 = _collect_articles("KO", None, rss)
check("RSS link preserved (untouched)",
      [a for a in arts4 if a["source"] == "Seeking Alpha"][0]["link"] == "https://seekingalpha.com/article/ko")


print(f"\n{'='*54}\n  {_passed} passed, {_failed} failed\n{'='*54}")
sys.exit(1 if _failed else 0)
