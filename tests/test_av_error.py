#!/usr/bin/env python3
"""
Tests for Alpha Vantage rate-limit / error detection (bug #9).

AV returns HTTP 200 even when throttled; the reason is under `Information`
(current daily-limit), `Note` (older), or `Error Message` (bad symbol). Both AV
fetchers must surface it. Mocks HTTP + key — no network.

Run:  python3 tests/test_av_error.py
"""
import os, sys
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import scripts.data_fetchers as df_mod
from scripts.data_fetchers import _av_error, alpha_vantage_price_history, alpha_vantage_news_sentiment

_passed = _failed = 0


def check(name, cond):
    global _passed, _failed
    _passed += 1 if cond else 0
    _failed += 0 if cond else 1
    print(f"  {'✓ PASS' if cond else '✗ FAIL'}  {name}")


class FakeResp:
    def __init__(self, data):
        self._d = data
    def json(self):
        return self._d
    def raise_for_status(self):
        pass


_LIMIT_MSG = ("We have detected your API key ... 25 requests per day. "
              "Please subscribe to a premium plan.")


def fetch_err(fetcher, payload):
    with mock.patch.object(df_mod, "get_api_key", return_value="KEY"), \
         mock.patch("requests.get", return_value=FakeResp(payload)):
        try:
            fetcher("TEST")
            return None
        except ValueError as e:
            return str(e)


# ── _av_error unit ────────────────────────────────────────────────────
print("\n_av_error:")
check("Information takes priority", _av_error({"Information": "limit", "Note": "n"}) == "limit")
check("Note when no Information", _av_error({"Note": "throttled"}) == "throttled")
check("Error Message for bad symbol", _av_error({"Error Message": "Invalid API call"}) == "Invalid API call")
check("clean payload → None", _av_error({"feed": []}) is None)


# ── daily-limit ('Information') surfaced by BOTH fetchers ──────────────
print("\ndaily-limit ('Information') surfaced (was 'Unknown' in news):")
perr = fetch_err(alpha_vantage_price_history, {"Information": _LIMIT_MSG})
check("price fetcher raises with the limit message", perr and "per day" in perr)
nerr = fetch_err(alpha_vantage_news_sentiment, {"Information": _LIMIT_MSG})
check("news fetcher raises with the limit message (not 'Unknown')",
      nerr and "per day" in nerr and "Unknown" not in nerr)

# ── bad symbol ('Error Message') ──────────────────────────────────────
print("\nbad symbol ('Error Message'):")
check("news surfaces Error Message",
      "Invalid" in (fetch_err(alpha_vantage_news_sentiment, {"Error Message": "Invalid API call"}) or ""))

# ── empty-but-clean payload → generic message, not a crash ────────────
print("\nempty payload:")
check("price: no data returned message",
      "no data" in (fetch_err(alpha_vantage_price_history, {}) or ""))
check("news: no feed returned message",
      "no feed" in (fetch_err(alpha_vantage_news_sentiment, {}) or ""))


print(f"\n{'='*54}\n  {_passed} passed, {_failed} failed\n{'='*54}")
sys.exit(1 if _failed else 0)
