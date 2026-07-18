#!/usr/bin/env python3
"""
Tests for the macro-calendar Stage 1 fix (bug #5).

Covers: correct Finnhub key path, impact mapping (text+numeric), HTTP status
classification, US country filter, source-level precedence (live supersedes the
approximate fallback for covered categories), coverage completeness, and the
"no events" vs "coverage incomplete" distinction.

Run:  python3 tests/test_macro_calendar.py   (no network; requests/config mocked)
"""
import os, sys
from datetime import date, timedelta
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import scripts.macro_calendar as mc
from scripts.macro_calendar import (
    get_economic_events, get_macro_summary, format_macro_summary,
    _impact_to_num, _classify_http, _fetch_finnhub_calendar,
)

_passed = _failed = 0


def check(name, cond):
    global _passed, _failed
    _passed += 1 if cond else 0
    _failed += 0 if cond else 1
    print(f"  {'✓ PASS' if cond else '✗ FAIL'}  {name}")


class FakeResp:
    def __init__(self, status, data=None):
        self.status_code = status
        self._d = data or {}
    def json(self):
        return self._d


# ── 1. impact mapping (Finnhub documents text; tolerate numbers) ──────
print("\nimpact mapping:")
check("'low' → 1", _impact_to_num("low") == 1)
check("'HIGH' → 3 (case-insensitive)", _impact_to_num("HIGH") == 3)
check("numeric 2 → 2", _impact_to_num(2) == 2)
check("garbage → 0", _impact_to_num("banana") == 0)
check("bool False → 0 (not treated as int)", _impact_to_num(False) == 0)


# ── 2. HTTP status classification ─────────────────────────────────────
print("\nHTTP classification:")
check("401 → auth", _classify_http(401) == "auth")
check("403 → premium", _classify_http(403) == "premium")
check("429 → rate_limit", _classify_http(429) == "rate_limit")
check("500 → provider", _classify_http(500) == "provider")


# ── 3. Correct key path: no key → not attempted (not an error) ────────
print("\nkey path (get_api_key, not config['api_keys']):")
with mock.patch("scripts.api_config.get_api_key", return_value=None):
    res = _fetch_finnhub_calendar(14)
check("no key → attempted False", res["attempted"] is False)
check("no key → success False, no error_class", res["success"] is False and res["error_class"] is None)


# ── 4. US filter + impact + 403 classification (mocked HTTP) ──────────
print("\nUS filter + premium 403:")
today = date.today()
feed = {"economicCalendar": [
    {"country": "US", "event": "CPI", "impact": "high", "time": (today + timedelta(days=3)).isoformat(), "estimate": "3.0%", "prev": "2.9%"},
    {"country": "AU", "event": "RBA Rate", "impact": "high", "time": (today + timedelta(days=2)).isoformat()},
    {"country": "US", "event": "Small thing", "impact": "low", "time": (today + timedelta(days=1)).isoformat()},
]}
with mock.patch("scripts.api_config.get_api_key", return_value="KEY"), \
     mock.patch("requests.get", return_value=FakeResp(200, feed)):
    res = _fetch_finnhub_calendar(14)
evs = res["events"]
check("only US kept (AU dropped)", all(e["affects"] == "US" for e in evs))
check("low-impact dropped", all(e["event"] != "Small thing" for e in evs))
check("US CPI kept", any(e["event"] == "CPI" for e in evs))
check("success True on 200", res["success"] is True)

with mock.patch("scripts.api_config.get_api_key", return_value="KEY"), \
     mock.patch("requests.get", return_value=FakeResp(403)):
    res403 = _fetch_finnhub_calendar(14)
check("403 → error_class 'premium'", res403["error_class"] == "premium")
check("403 → success False", res403["success"] is False)


# ── 5. CRITICAL: live CPI (revised date) supersedes fallback CPI ──────
print("\nsource precedence (the headline test):")
cutoff = (today + timedelta(days=14)).isoformat()
live = {"attempted": True, "success": True, "http_status": 200, "error_class": None,
        "coverage_start": today.isoformat(), "coverage_end": cutoff,
        "events": [{"event": "CPI", "category": "FINNHUB", "date": (today + timedelta(days=7)).isoformat(),
                    "days_until": 7, "impact": "HIGH", "affects": "US",
                    "source": "finnhub", "date_confidence": "SCHEDULED"}]}
fallback = ([
    {"event": "CPI Report", "category": "CPI", "date": (today + timedelta(days=4)).isoformat(),
     "days_until": 4, "impact": "HIGH", "source": "hardcoded_fallback", "date_confidence": "APPROXIMATE"},
    {"event": "Triple Witching (OPEX)", "category": "OPEX", "date": (today + timedelta(days=6)).isoformat(),
     "days_until": 6, "impact": "MEDIUM", "source": "hardcoded_fallback", "date_confidence": "APPROXIMATE"},
], {"FOMC": "2026-12-16", "CPI": "2026-12-10", "JOBS": "2026-12-04", "OPEX": "2026-12-18"})

with mock.patch.object(mc, "_fetch_finnhub_calendar", return_value=live), \
     mock.patch.object(mc, "_hardcoded_events", return_value=fallback):
    eco = get_economic_events(14)
dates = {(e["event"], e["date"]) for e in eco["events"]}
live_cpi = ("CPI", (today + timedelta(days=7)).isoformat())
fallback_cpi = ("CPI Report", (today + timedelta(days=4)).isoformat())
opex = ("Triple Witching (OPEX)", (today + timedelta(days=6)).isoformat())
check("live CPI present", live_cpi in dates)
check("fallback CPI SUPPRESSED (not both)", fallback_cpi not in dates)
check("OPEX kept (Finnhub doesn't cover it)", opex in dates)
check("no fallback CPI source in final set",
      all(not (e["source"] == "hardcoded_fallback" and e["event"] == "CPI Report") for e in eco["events"]))


# ── 6. Coverage completeness (real hardcoded dates end 2026-12) ───────
print("\ncoverage completeness:")
with mock.patch("scripts.api_config.get_api_key", return_value=None):
    near = get_economic_events(14)     # cutoff well within 2026 → complete
    far = get_economic_events(400)     # cutoff into 2027 → incomplete
check("14-day window → coverage_complete True", near["coverage_complete"] is True)
check("14-day window → no coverage warning", near["coverage_warnings"] == [])
check("400-day window → coverage_complete False", far["coverage_complete"] is False)
check("400-day window → emits a coverage warning", len(far["coverage_warnings"]) == 1)


# ── 7. Soft note on premium failure + format distinguishes states ─────
print("\nobservability (soft note + no-events vs incomplete):")
with mock.patch.object(mc, "_fetch_finnhub_calendar", return_value=res403), \
     mock.patch.object(mc, "_hardcoded_events", return_value=([], {"FOMC": "2026-12-16", "CPI": "2026-12-10", "JOBS": "2026-12-04", "OPEX": "2026-12-18"})):
    summ = get_macro_summary(days_ahead=14)
check("premium failure → LOW CALENDAR_SOURCE flag",
      any(f["flag"] == "CALENDAR_SOURCE" and "paid tier" in f["message"] for f in summ["risk_flags"]))
check("empty events + complete coverage → 'coverage is complete'",
      "coverage is complete" in format_macro_summary({"economic_events": [], "coverage_complete": True, "risk_flags": []}))
check("empty events + incomplete → 'INCOMPLETE'",
      "INCOMPLETE" in format_macro_summary({"economic_events": [], "coverage_complete": False,
                                            "coverage_warnings": ["short"], "risk_flags": []}))


print(f"\n{'='*52}\n  {_passed} passed, {_failed} failed\n{'='*52}")
sys.exit(1 if _failed else 0)
