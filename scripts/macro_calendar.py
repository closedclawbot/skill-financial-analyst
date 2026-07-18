"""
Macro Calendar — Upcoming earnings, economic events, and Fed decisions.

Surfaces timing-critical events that affect portfolio decisions:
  - Earnings dates for held stocks (don't sell right before a catalyst)
  - CPI / jobs reports / GDP releases
  - Fed rate decisions (FOMC)
  - Options expiration dates

Data sources:
  - yfinance: Next earnings date per ticker
  - Finnhub: Economic calendar (free tier)
  - Hardcoded: Known FOMC dates, CPI schedule, options expiry (triple witching)

Usage:
    from scripts.macro_calendar import get_earnings_calendar, get_economic_events
    from scripts.macro_calendar import get_macro_summary, days_until_event

    # Earnings for specific tickers
    earnings = get_earnings_calendar(["AAPL", "MSFT", "NVDA"])

    # Upcoming economic events
    events = get_economic_events(days_ahead=14)

    # Full summary for portfolio review header
    summary = get_macro_summary(tickers=["AAPL", "MSFT"], days_ahead=14)
"""
import os, sys
from datetime import datetime, date, timedelta

_project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# ═══════════════════════════════════════════════════════════════════════
#  HARDCODED CALENDARS (updated periodically — reliable fallback)
# ═══════════════════════════════════════════════════════════════════════

# 2025-2026 FOMC meeting dates (announcement days)
FOMC_DATES = [
    # 2025
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18",
    "2025-07-30", "2025-09-17", "2025-10-29", "2025-12-17",
    # 2026
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-16",
]

# 2025-2026 CPI release dates (approximate — BLS publishes ~10th-14th of month)
CPI_DATES = [
    "2025-01-15", "2025-02-12", "2025-03-12", "2025-04-10", "2025-05-13",
    "2025-06-11", "2025-07-11", "2025-08-12", "2025-09-10", "2025-10-14",
    "2025-11-12", "2025-12-10",
    "2026-01-14", "2026-02-11", "2026-03-11", "2026-04-14", "2026-05-12",
    "2026-06-10", "2026-07-14", "2026-08-12", "2026-09-15", "2026-10-13",
    "2026-11-10", "2026-12-10",
]

# Jobs reports (first Friday of each month, usually)
JOBS_DATES = [
    "2025-01-10", "2025-02-07", "2025-03-07", "2025-04-04", "2025-05-02",
    "2025-06-06", "2025-07-03", "2025-08-01", "2025-09-05", "2025-10-03",
    "2025-11-07", "2025-12-05",
    "2026-01-09", "2026-02-06", "2026-03-06", "2026-04-03", "2026-05-01",
    "2026-06-05", "2026-07-02", "2026-08-07", "2026-09-04", "2026-10-02",
    "2026-11-06", "2026-12-04",
]

# Triple witching / quad witching (3rd Friday of March, June, Sept, Dec)
OPEX_DATES = [
    "2025-03-21", "2025-06-20", "2025-09-19", "2025-12-19",
    "2026-03-20", "2026-06-19", "2026-09-18", "2026-12-18",
]


def _parse_date(d):
    """Parse a date string to a date object."""
    if isinstance(d, date):
        return d
    if isinstance(d, datetime):
        return d.date()
    try:
        return datetime.strptime(str(d)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def days_until_event(event_date):
    """Return number of calendar days from today to the event."""
    d = _parse_date(event_date)
    if not d:
        return None
    return (d - date.today()).days


# ═══════════════════════════════════════════════════════════════════════
#  EARNINGS CALENDAR
# ═══════════════════════════════════════════════════════════════════════

def get_earnings_calendar(tickers):
    """
    Get next earnings date for each ticker via yfinance.

    Returns: list of {ticker, earnings_date, days_until, is_upcoming}
    """
    results = []
    try:
        import yfinance as yf
    except ImportError:
        return results

    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            cal = stock.calendar
            earn_date = None

            if cal is not None:
                # yfinance returns different formats depending on version
                if isinstance(cal, dict):
                    ed = cal.get("Earnings Date")
                    if ed:
                        if isinstance(ed, list) and len(ed) > 0:
                            earn_date = ed[0]
                        else:
                            earn_date = ed
                elif hasattr(cal, "iloc"):
                    # DataFrame format
                    try:
                        earn_date = cal.iloc[0, 0] if cal.shape[0] > 0 else None
                    except Exception:
                        pass

            # Fallback: try earnings_dates property
            if earn_date is None:
                try:
                    edates = stock.earnings_dates
                    if edates is not None and len(edates) > 0:
                        # Get the nearest future date
                        today = datetime.now()
                        future = [d for d in edates.index if d >= today]
                        if future:
                            earn_date = future[0]
                except Exception:
                    pass

            if earn_date is not None:
                d = _parse_date(earn_date)
                if d:
                    days = (d - date.today()).days
                    results.append({
                        "ticker": ticker,
                        "earnings_date": d.isoformat(),
                        "days_until": days,
                        "is_upcoming": 0 <= days <= 14,
                        "is_imminent": 0 <= days <= 3,
                    })
        except Exception:
            continue

    return sorted(results, key=lambda x: x.get("days_until", 999))


# ═══════════════════════════════════════════════════════════════════════
#  ECONOMIC EVENTS
# ═══════════════════════════════════════════════════════════════════════

# Hardcoded fallback categories: (key, dates, name, impact, description, affects).
# Dates are APPROXIMATE and go stale — Stage 2 replaces them with live official
# sources (BLS ICS, Fed, OPEX holiday-aware generator). Do NOT hand-patch dates.
_HARDCODED_SPECS = [
    ("FOMC", FOMC_DATES, "FOMC Rate Decision", "HIGH",
     "Federal Reserve interest rate decision and economic projections",
     "All sectors — especially REITs, banks, growth stocks"),
    ("CPI", CPI_DATES, "CPI Report", "HIGH",
     "Consumer Price Index — key inflation measure",
     "Rate-sensitive sectors, growth vs value rotation"),
    ("JOBS", JOBS_DATES, "Jobs Report (NFP)", "HIGH",
     "Non-Farm Payrolls — labor market health",
     "Consumer discretionary, industrials, broad market sentiment"),
    ("OPEX", OPEX_DATES, "Triple Witching (OPEX)", "MEDIUM",
     "Index futures, index options, stock options all expire — high volume day",
     "Elevated volatility, especially last 2 hours of trading"),
]

# Categories Finnhub's economic calendar authoritatively covers (NOT OPEX,
# which is a market-structure event Finnhub doesn't track).
_FINNHUB_MACRO_CATEGORIES = {"FOMC", "CPI", "JOBS"}

_IMPACT_MAP = {"low": 1, "medium": 2, "high": 3}


def _impact_to_num(v):
    """Finnhub documents impact as text (low/medium/high); tolerate numbers too."""
    if isinstance(v, bool):
        return 0
    if isinstance(v, (int, float)):
        return int(v)
    if isinstance(v, str):
        return _IMPACT_MAP.get(v.strip().lower(), 0)
    return 0


def _classify_http(status):
    """Map an HTTP status to an actionable error class (not all failures are premium)."""
    if status == 401:
        return "auth"          # invalid key
    if status == 403:
        return "premium"       # missing entitlement (economic calendar is paid)
    if status == 429:
        return "rate_limit"
    return "provider"          # 5xx / anything else


def _hardcoded_events(days_ahead):
    """Build fallback events tagged APPROXIMATE, plus per-category coverage_end."""
    today = date.today()
    cutoff = today + timedelta(days=days_ahead)
    events, coverage_end = [], {}
    for cat, dates, name, impact, desc, affects in _HARDCODED_SPECS:
        parsed = sorted(d for d in (_parse_date(x) for x in dates) if d)
        coverage_end[cat] = parsed[-1].isoformat() if parsed else None
        for dt in parsed:
            if today <= dt <= cutoff:
                events.append({
                    "event": name, "category": cat, "date": dt.isoformat(),
                    "days_until": (dt - today).days, "impact": impact,
                    "description": desc, "affects": affects,
                    "source": "hardcoded_fallback", "date_confidence": "APPROXIMATE",
                })
    return events, coverage_end


def _fetch_finnhub_calendar(days_ahead=14, config=None):
    """Fetch US economic events from Finnhub's economic calendar (PREMIUM endpoint).

    Returns a STRUCTURED status dict — not a bare list — so callers can tell
    "covered, no events" from auth/premium/rate-limit/network failure:
        {attempted, success, http_status, error_class, events, coverage_start/end}
    """
    from scripts.api_config import get_api_key
    today = date.today()
    cutoff = today + timedelta(days=days_ahead)
    result = {"attempted": False, "success": False, "http_status": None,
              "error_class": None, "events": [],
              "coverage_start": today.isoformat(), "coverage_end": None}

    key = get_api_key("finnhub", config)
    if not key:
        return result  # no key → not attempted (not an error, not premium)

    result["attempted"] = True
    try:
        import requests
        r = requests.get(
            "https://finnhub.io/api/v1/calendar/economic",
            params={"from": today.isoformat(), "to": cutoff.isoformat(), "token": key},
            timeout=10,
        )
        result["http_status"] = r.status_code
        if r.status_code != 200:
            result["error_class"] = _classify_http(r.status_code)
            return result
        data = r.json()
        for item in data.get("economicCalendar", []):
            if str(item.get("country", "")).strip().upper() not in ("US", "USA", "UNITED STATES"):
                continue
            imp = _impact_to_num(item.get("impact", 0))
            if imp < 2:  # skip low-impact
                continue
            dt = _parse_date(item.get("time", item.get("date", "")))
            if not dt or not (today <= dt <= cutoff):
                continue
            result["events"].append({
                "event": item.get("event", "Economic Event"),
                "category": "FINNHUB", "date": dt.isoformat(),
                "days_until": (dt - today).days,
                "impact": "HIGH" if imp >= 3 else "MEDIUM",
                "description": f"Prev: {item.get('prev', 'N/A')} | Est: {item.get('estimate', 'N/A')}",
                "affects": "US", "source": "finnhub", "date_confidence": "SCHEDULED",
            })
        result["success"] = True
        # A successful 200 covers the whole queried window (even with 0 events).
        result["coverage_end"] = cutoff.isoformat()
    except Exception:
        result["error_class"] = "network"
    return result


def get_economic_events(days_ahead=14, config=None):
    """
    Upcoming US economic events with source precedence and coverage tracking.

    Live source (Finnhub, if entitled) takes precedence over the approximate
    hardcoded fallback FOR THE CATEGORIES IT COVERS (FOMC/CPI/JOBS) — so a
    revised live CPI date replaces the wrong fallback date rather than both
    appearing. OPEX is not covered by Finnhub, so it stays from the fallback.

    Returns a dict: {events, query_start, query_end, coverage_complete,
                     coverage_warnings, source_status}.
    """
    today = date.today()
    cutoff = today + timedelta(days=days_ahead)
    hard_events, hard_cov = _hardcoded_events(days_ahead)
    fh = _fetch_finnhub_calendar(days_ahead, config)

    events = []
    effective_cov = dict(hard_cov)  # per-category coverage end
    if fh["success"]:
        # Finnhub authoritatively covers US macro for the window → suppress the
        # fallback macro events entirely, keep only categories it doesn't cover.
        events.extend(fh["events"])
        for cat in _FINNHUB_MACRO_CATEGORIES:
            effective_cov[cat] = fh["coverage_end"]
        events.extend(e for e in hard_events if e["category"] not in _FINNHUB_MACRO_CATEGORIES)
    else:
        events.extend(hard_events)

    # Exact dedup only AFTER precedence (by event name + date).
    seen, deduped = set(), []
    for e in sorted(events, key=lambda x: x.get("days_until", 999)):
        k = (e.get("event"), e.get("date"))
        if k not in seen:
            seen.add(k)
            deduped.append(e)

    # Coverage: complete only if EVERY category reaches the cutoff.
    incomplete = [cat for cat, cov in effective_cov.items()
                  if cov is None or _parse_date(cov) < cutoff]
    warnings = []
    if incomplete:
        last = min((effective_cov[c] for c in incomplete if effective_cov[c]), default="unknown")
        warnings.append(
            f"Economic calendar coverage incomplete through {cutoff.isoformat()} "
            f"(short: {', '.join(sorted(incomplete))}; fallback ends ~{last}). "
            f"Update Stage-2 live sources (BLS/Fed)."
        )

    return {
        "events": deduped,
        "query_start": today.isoformat(),
        "query_end": cutoff.isoformat(),
        "coverage_complete": not incomplete,
        "coverage_warnings": warnings,
        "source_status": {
            "finnhub": {k: fh[k] for k in ("attempted", "success", "http_status",
                                            "error_class", "coverage_start", "coverage_end")},
            "hardcoded_fallback": {"coverage_end": hard_cov},
        },
    }


# ═══════════════════════════════════════════════════════════════════════
#  MACRO SUMMARY (for portfolio review header)
# ═══════════════════════════════════════════════════════════════════════

def get_macro_summary(tickers=None, days_ahead=14, config=None):
    """
    Build a complete macro summary for the portfolio review.

    Returns dict with earnings_calendar, economic_events (list), risk_flags,
    plus calendar coverage/observability fields (coverage_complete,
    coverage_warnings, calendar_source_status).
    """
    tickers = tickers or []
    earnings = get_earnings_calendar(tickers) if tickers else []
    eco = get_economic_events(days_ahead, config)
    events = eco["events"]

    risk_flags = []

    # Imminent earnings
    imminent = [e for e in earnings if e.get("is_imminent")]
    if imminent:
        tickers_str = ", ".join(e["ticker"] for e in imminent)
        risk_flags.append({
            "flag": "EARNINGS_IMMINENT", "severity": "HIGH",
            "message": f"Earnings within 3 days: {tickers_str} — expect volatility, review position sizing",
        })

    upcoming = [e for e in earnings if e.get("is_upcoming") and not e.get("is_imminent")]
    if upcoming:
        tickers_str = ", ".join(f"{e['ticker']} ({e['days_until']}d)" for e in upcoming)
        risk_flags.append({
            "flag": "EARNINGS_UPCOMING", "severity": "MEDIUM",
            "message": f"Earnings within 14 days: {tickers_str}",
        })

    # High-impact economic events (flag approximate fallback dates honestly)
    for ev in [e for e in events if e.get("impact") == "HIGH" and e.get("days_until", 99) <= 5]:
        approx = (" — approximate fallback date; live calendar unavailable"
                  if ev.get("date_confidence") == "APPROXIMATE" else "")
        risk_flags.append({
            "flag": "MACRO_EVENT", "severity": "HIGH",
            "message": f"{ev['event']} in {ev['days_until']} day(s) ({ev['date']}) — {ev.get('affects', '')}{approx}",
        })

    # One soft note if a live-calendar fetch was attempted and failed (macro is
    # fetched once per summary, so this never spams).
    fh = eco["source_status"]["finnhub"]
    if fh.get("attempted") and not fh.get("success"):
        note = {"premium": "requires Finnhub paid tier", "auth": "invalid Finnhub key",
                "rate_limit": "Finnhub rate-limited", "provider": "Finnhub server error",
                "network": "network error"}.get(fh.get("error_class"), fh.get("error_class") or "unavailable")
        risk_flags.append({
            "flag": "CALENDAR_SOURCE", "severity": "LOW",
            "message": f"Live economic calendar unavailable ({note}); using approximate fallback dates.",
        })
    for w in eco["coverage_warnings"]:
        risk_flags.append({"flag": "CALENDAR_COVERAGE", "severity": "LOW", "message": w})

    return {
        "earnings_calendar": earnings,
        "economic_events": events,                       # list (portfolio-review compat)
        "coverage_complete": eco["coverage_complete"],
        "coverage_warnings": eco["coverage_warnings"],
        "calendar_source_status": eco["source_status"],
        "risk_flags": risk_flags,
        "checked_at": datetime.now().isoformat(),
    }


def format_macro_summary(summary):
    """Format the macro summary for console output."""
    lines = []
    _h = lines.append

    _h(f"  {'─' * 60}")
    _h(f"  MACRO CALENDAR")
    _h(f"  {'─' * 60}")

    # Risk flags first
    flags = summary.get("risk_flags", [])
    if flags:
        for f in flags:
            icon = "🔴" if f["severity"] == "HIGH" else "🟡"
            _h(f"  {icon} {f['message']}")
        _h("")

    # Earnings
    earnings = summary.get("earnings_calendar", [])
    if earnings:
        _h(f"  UPCOMING EARNINGS:")
        for e in earnings:
            days = e["days_until"]
            marker = " *** IMMINENT" if e.get("is_imminent") else ""
            if days < 0:
                _h(f"    {e['ticker']:<8} {e['earnings_date']}  ({abs(days)}d ago){marker}")
            else:
                _h(f"    {e['ticker']:<8} {e['earnings_date']}  (in {days}d){marker}")
        _h("")

    # Economic events
    events = summary.get("economic_events", [])
    if events:
        _h(f"  ECONOMIC EVENTS (next 14 days):")
        for ev in events[:8]:
            impact = ev.get("impact", "?")
            conf = "  ~approx" if ev.get("date_confidence") == "APPROXIMATE" else ""
            _h(f"    [{impact}] {ev['event']} — {ev['date']} (in {ev['days_until']}d){conf}")
    elif summary.get("coverage_complete", True):
        _h(f"  No major economic events found; calendar coverage is complete.")
    else:
        _h(f"  No events available; calendar coverage is INCOMPLETE (see warnings).")

    for w in summary.get("coverage_warnings", []):
        _h(f"  ⚠ {w}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Macro Calendar")
    parser.add_argument("tickers", nargs="*", help="Tickers to check earnings for")
    parser.add_argument("--days", type=int, default=14, help="Days ahead to scan (default: 14)")
    args = parser.parse_args()

    summary = get_macro_summary(tickers=args.tickers, days_ahead=args.days)
    print(format_macro_summary(summary))


if __name__ == "__main__":
    main()
