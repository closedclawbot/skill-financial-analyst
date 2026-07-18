#!/usr/bin/env python3
"""
Tests for the sec_edgar_filings cleanup (bugs #6 / #7 + #6a, option b).

Mocks requests + config so no network is touched. Verifies:
  - exactly 2 HTTP calls (not 4), and the ticker map is cached across tickers
  - User-Agent carries the CONFIGURED contact email
  - missing / null email raises ValueError (no placeholder, no crash) and makes
    no HTTP calls
  - document_url is constructed from cik + accession + primaryDocument
  - sec_edgar is out of the 'fundamentals' chain and in its own 'filings' one

Run:  .venv/bin/python tests/test_sec_edgar.py   (or plain python3 — no deps)
"""
import os, sys
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import scripts.data_fetchers as df
from scripts.data_fetchers import sec_edgar_filings, get_fetchers, _sec_ticker_map
from scripts.api_config import FALLBACK_CHAINS

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


class FakeResp:
    def __init__(self, data):
        self._d = data
    def json(self):
        return self._d
    def raise_for_status(self):
        pass


_SUBMISSIONS = {
    "name": "Apple Inc.",
    "filings": {"recent": {
        "form": ["10-K", "8-K"],
        "filingDate": ["2024-11-01", "2024-10-01"],
        "primaryDocument": ["aapl-20240928.htm", "d123.htm"],
        "accessionNumber": ["0000320193-24-000123", "0000320193-24-000100"],
    }},
}
_TICKERS = {
    "0": {"ticker": "AAPL", "cik_str": 320193},
    "1": {"ticker": "MSFT", "cik_str": 789019},
}


def make_get(calls):
    def _get(url, headers=None, timeout=None, **kw):
        calls.append((url, (headers or {}).get("User-Agent")))
        if "company_tickers.json" in url:
            return FakeResp(_TICKERS)
        if "submissions" in url:
            return FakeResp(_SUBMISSIONS)
        return FakeResp({})
    return _get


def _cfg(email):
    return {"apis": {"sec_edgar": {"user_agent_email": email}}}


# ── 1. Call count, caching, UA, document_url (email configured) ───────
print("\nemail configured — call count / cache / UA / URL:")
_sec_ticker_map.cache_clear()
os.environ.pop("SEC_EDGAR_USER_AGENT_EMAIL", None)
calls = []
with mock.patch("scripts.api_config.load_config", return_value=_cfg("test@example.com")), \
     mock.patch("requests.get", side_effect=make_get(calls)):
    res = sec_edgar_filings("AAPL")
    n_after_first = len(calls)
    res2 = sec_edgar_filings("MSFT")
    n_after_second = len(calls)

check("first ticker → exactly 2 HTTP calls (was 4)", n_after_first == 2)
check("second ticker → +1 call (ticker map cached)", n_after_second == 3)
check("User-Agent carries configured email",
      all(ua == "financial-analysis-skill test@example.com" for _, ua in calls))
check("document_url built from cik+accession+doc",
      res["recent_filings"][0]["document_url"]
      == "https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl-20240928.htm")
check("primary_document preserved", res["recent_filings"][0]["primary_document"] == "aapl-20240928.htm")
check("all recent forms returned (no silent 10-K filter)",
      [f["form"] for f in res["recent_filings"]] == ["10-K", "8-K"])


# ── 2. Missing email → ValueError, no HTTP ────────────────────────────
print("\nmissing email — must raise, no HTTP:")
_sec_ticker_map.cache_clear()
os.environ.pop("SEC_EDGAR_USER_AGENT_EMAIL", None)
calls2 = []
raised = False
with mock.patch("scripts.api_config.load_config", return_value=_cfg("")), \
     mock.patch("requests.get", side_effect=make_get(calls2)):
    try:
        sec_edgar_filings("AAPL")
    except ValueError:
        raised = True
check("raises ValueError when no contact email", raised)
check("no HTTP calls made when email missing", len(calls2) == 0)


# ── 3. null email value → ValueError, not AttributeError ──────────────
print("\nnull email value — must not crash on .strip():")
_sec_ticker_map.cache_clear()
os.environ.pop("SEC_EDGAR_USER_AGENT_EMAIL", None)
raised_value = False
crashed = False
with mock.patch("scripts.api_config.load_config", return_value=_cfg(None)), \
     mock.patch("requests.get", side_effect=make_get([])):
    try:
        sec_edgar_filings("AAPL")
    except ValueError:
        raised_value = True
    except AttributeError:
        crashed = True
check("null email → ValueError (the `or ''` guard works)", raised_value)
check("null email → NOT AttributeError", not crashed)


# ── 4. Registry / fetcher wiring ──────────────────────────────────────
print("\nregistry / fetcher wiring:")
check("sec_edgar NOT in fundamentals chain", "sec_edgar" not in FALLBACK_CHAINS["fundamentals"])
check("filings chain is [sec_edgar]", FALLBACK_CHAINS.get("filings") == ["sec_edgar"])
f = get_fetchers("AAPL")
check("get_fetchers: sec_edgar NOT under fundamentals", "sec_edgar" not in f["fundamentals"])
check("get_fetchers: filings category exists with sec_edgar",
      "filings" in f and "sec_edgar" in f["filings"])


# ── Summary ───────────────────────────────────────────────────────────
print(f"\n{'='*50}")
print(f"  {_passed} passed, {_failed} failed")
print(f"{'='*50}")
sys.exit(1 if _failed else 0)
