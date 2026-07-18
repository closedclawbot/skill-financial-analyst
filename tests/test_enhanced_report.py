#!/usr/bin/env python3
"""
Tests for the enhanced report transparency & source attribution changes.

Tests:
1. Scoring — verify rating_note and source fields in all 17 factors
2. Report formatter — verify _format_position_detail() produces expected sections
3. Cache simulation — verify result dict has all new fields
4. Article sentiment flags — verify 🟢/🟡/🔴 assignment
"""
import os, sys, json

_project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from scripts.scoring import compute_composite_score, _score_fundamental, _score_sentiment


def test_fundamental_rating_notes():
    """Test that all 10 fundamental factors have rating_note."""
    print("=" * 60)
    print("TEST 1: Fundamental factors — rating_note")
    print("=" * 60)

    fundamentals = {
        "pe_ratio": 22.5,
        "pb_ratio": 3.2,
        "revenue_growth": 0.12,
        "earnings_growth": 0.18,
        "profit_margin": 0.25,
        "debt_to_equity": 0.8,
        "free_cash_flow": 8e9,
        "roe": 0.22,
    }
    analyst = {"buy": 10, "strong_buy": 5, "hold": 6, "sell": 2, "strong_sell": 1}
    earnings = {"beat_count": 3, "miss_count": 1, "surprise_avg": 4.5}

    result = _score_fundamental(fundamentals, analyst=analyst, earnings=earnings)
    details = result["factor_details"]

    expected_factors = [
        "pe_ratio", "pb_ratio", "revenue_growth", "eps_growth",
        "profit_margin", "debt_to_equity", "free_cash_flow", "roe",
        "analyst_consensus", "earnings_surprises",
    ]

    all_ok = True
    for key in expected_factors:
        factor = details.get(key, {})
        has_note = "rating_note" in factor
        note = factor.get("rating_note", "MISSING")
        score = factor.get("score", "?")
        status = "✓" if has_note else "✗"
        if not has_note:
            all_ok = False
        print(f"  {status} {key:<25} score={score:<5} note: {note}")

    print(f"\n  Result: {'PASS' if all_ok else 'FAIL'} — {sum(1 for k in expected_factors if 'rating_note' in details.get(k, {}))}/10 factors have rating_note")
    return all_ok


def test_sentiment_rating_notes_and_sources():
    """Test that all 7 sentiment factors have rating_note and source."""
    print("\n" + "=" * 60)
    print("TEST 2: Sentiment factors — rating_note + source")
    print("=" * 60)

    reddit = {"mentions": 250, "mentions_24h_ago": 180, "rank": 8}
    stocktwits = {"bull_pct": 72.5, "messages_count": 150}
    news = {"avg_sentiment": 0.18, "article_count": 12, "source": "Alpha Vantage"}
    tradingview = {"recommendation": "BUY", "buy_count": 16, "neutral_count": 7, "sell_count": 3}
    rss = {"mention_count": 6}
    insider = {"buys_last_50": 5, "sells_last_50": 12, "net_insider_signal": "bearish"}
    congress = {"congress_trades": [{"type": "Purchase"}, {"type": "Sale"}, {"type": "Purchase"}]}

    result = _score_sentiment(
        reddit=reddit, stocktwits=stocktwits, news=news,
        tradingview=tradingview, rss=rss, insider=insider, congress=congress,
    )
    details = result["factor_details"]

    expected_factors = [
        "reddit_sentiment", "stocktwits_sentiment", "news_sentiment",
        "tradingview_consensus", "rss_buzz", "insider_activity", "congress_trades",
    ]

    all_ok = True
    for key in expected_factors:
        factor = details.get(key, {})
        has_note = "rating_note" in factor
        has_source = "source" in factor
        note = factor.get("rating_note", "MISSING")
        source = factor.get("source", "MISSING")
        score = factor.get("score", "?")
        status = "✓" if (has_note and has_source) else "✗"
        if not (has_note and has_source):
            all_ok = False
        print(f"  {status} {key:<28} score={score:<5} source={source:<25} note: {note}")

    notes_ok = sum(1 for k in expected_factors if 'rating_note' in details.get(k, {}))
    sources_ok = sum(1 for k in expected_factors if 'source' in details.get(k, {}))
    print(f"\n  Result: {'PASS' if all_ok else 'FAIL'} — {notes_ok}/7 rating_notes, {sources_ok}/7 sources")
    return all_ok


def test_composite_score_structure():
    """Test that compute_composite_score returns full factor breakdown."""
    print("\n" + "=" * 60)
    print("TEST 3: Composite score — full sub_scores structure")
    print("=" * 60)

    result = compute_composite_score(
        fundamentals={"pe_ratio": 18, "pb_ratio": 2.5, "revenue_growth": 0.1,
                       "profit_margin": 0.15, "roe": 0.18},
        technicals={"tech_score": 6.5, "rsi_14": 55, "macd_bullish": True,
                     "above_sma50": True, "above_sma200": True, "bb_position": 0.6},
        tradingview={"recommendation": "BUY", "buy_count": 14, "neutral_count": 8, "sell_count": 4},
        reddit={"mentions": 100, "mentions_24h_ago": 80},
        stocktwits={"bull_pct": 65, "messages_count": 80},
        news={"avg_sentiment": 0.12, "article_count": 8, "source": "Finnhub"},
    )

    # Check structure
    assert "sub_scores" in result, "Missing sub_scores"
    for cat in ["fundamental", "technical", "sentiment"]:
        assert cat in result["sub_scores"], f"Missing sub_scores[{cat}]"
        sub = result["sub_scores"][cat]
        assert "score" in sub, f"Missing sub_scores[{cat}].score"
        assert "weight" in sub, f"Missing sub_scores[{cat}].weight"
        assert "factors" in sub, f"Missing sub_scores[{cat}].factors"
        assert "confidence" in sub, f"Missing sub_scores[{cat}].confidence"

    # Check factor-level detail
    fund_factors = result["sub_scores"]["fundamental"]["factors"]
    sent_factors = result["sub_scores"]["sentiment"]["factors"]

    fund_with_notes = sum(1 for f in fund_factors.values() if isinstance(f, dict) and "rating_note" in f)
    sent_with_notes = sum(1 for f in sent_factors.values() if isinstance(f, dict) and "rating_note" in f)
    sent_with_source = sum(1 for f in sent_factors.values() if isinstance(f, dict) and "source" in f)

    print(f"  ✓ composite_score: {result['composite_score']}/10 ({result['rating']})")
    print(f"  ✓ Fundamental: {result['sub_scores']['fundamental']['score']}/10 — {fund_with_notes}/10 factors with rating_note")
    print(f"  ✓ Technical: {result['sub_scores']['technical']['score']}/10")
    print(f"  ✓ Sentiment: {result['sub_scores']['sentiment']['score']}/10 — {sent_with_notes}/7 factors with rating_note, {sent_with_source}/7 with source")
    print(f"\n  Result: PASS")
    return True


def test_position_detail_formatter():
    """Test that _format_position_detail produces all expected sections."""
    print("\n" + "=" * 60)
    print("TEST 4: Position detail formatter — all sections present")
    print("=" * 60)

    from scripts.run_portfolio_review import _format_position_detail

    # Build a mock position dict
    mock_position = {
        "ticker": "AAPL",
        "shares": 100,
        "avg_cost": 150.50,
        "current_price": 230.50,
        "position_value": 23050.0,
        "cost_basis_total": 15050.0,
        "pnl_per_share": 80.0,
        "pnl_pct": 53.16,
        "total_pnl": 8000.0,
        "composite_score": 7.2,
        "rating": "BUY",
        "action": "HOLD (strong — let it run)",
        "confidence": "HIGH",
        "sector": "Technology",
        "sector_modifier": 0.15,
        "from_cache": False,
        "fundamentals_summary": {"name": "Apple Inc.", "sector": "Technology"},
        "sub_scores": {
            "fundamental": {
                "score": 7.1, "weight": 0.4, "weighted": 2.84, "confidence": "HIGH",
                "factors": {
                    "pe_ratio": {"value": 28.5, "score": 5, "rating_note": "Elevated — above market average"},
                    "pb_ratio": {"value": 45.2, "score": 2, "rating_note": "Very expensive relative to book value"},
                    "revenue_growth": {"value": 4.3, "score": 6, "rating_note": "Modest growth — in line with economy"},
                    "eps_growth": {"value": 12.0, "score": 7, "rating_note": "Healthy earnings growth"},
                    "profit_margin": {"value": 26.3, "score": 8, "rating_note": "Strong margins — competitive advantage"},
                    "debt_to_equity": {"value": 1.8, "score": 5, "rating_note": "High debt — elevated financial risk"},
                    "free_cash_flow": {"value": "$100.24B", "score": 9, "rating_note": "Exceptional cash generation — >$10B FCF"},
                    "roe": {"value": 157.4, "score": 9, "rating_note": "Exceptional ROE — very efficient capital use"},
                    "analyst_consensus": {"buy": 30, "hold": 8, "sell": 2, "buy_pct": 75, "score": 9, "rating_note": "Strong buy consensus — 70%+ analysts bullish"},
                    "earnings_surprises": {"beat_count": 4, "miss_count": 0, "surprise_avg_pct": 5.2, "score": 9, "rating_note": "Consistently beats estimates by wide margin"},
                },
            },
            "technical": {
                "score": 6.8, "weight": 0.3, "weighted": 2.04, "confidence": "HIGH",
                "factors": {
                    "tech_score": 6.8, "rsi": 55.2, "macd_bullish": True,
                    "above_sma50": True, "above_sma200": True, "bb_position": 0.62,
                    "volume_ratio": 1.1, "adx": 22.5,
                },
            },
            "sentiment": {
                "score": 7.5, "weight": 0.3, "weighted": 2.25, "confidence": "MEDIUM",
                "factors": {
                    "reddit_sentiment": {"mentions": 450, "trend": 1.5, "rank": 12, "score": 7, "source": "ApeWisdom", "rating_note": "Mentions rising — growing attention"},
                    "stocktwits_sentiment": {"bull_pct": 72, "messages": 200, "score": 7, "source": "StockTwits", "rating_note": "Bullish — 72% bull sentiment"},
                    "news_sentiment": {"avg_sentiment": 0.23, "articles": 15, "score": 7, "source": "Alpha Vantage", "rating_note": "Mildly positive — avg sentiment +0.23"},
                    "tradingview_consensus": {"recommendation": "BUY", "buy_count": 16, "neutral_count": 8, "sell_count": 2, "score": 7.5, "source": "TradingView (tradingview-ta)", "rating_note": "Buy — majority of indicators bullish (16B/8N/2S)"},
                    "rss_buzz": {"mention_count": 8, "score": 7, "source": "Seeking Alpha / RSS feeds", "rating_note": "Good coverage — 8 mentions"},
                    "insider_activity": {"buys": 3, "sells": 12, "signal": "bearish", "score": 3, "source": "Finnhub", "rating_note": "Heavy insider selling — 3 buys vs 12 sells"},
                    "congress_trades": {"value": None, "score": 5, "source": "Mboum Finance", "rating_note": "No Congress trade data available"},
                },
            },
        },
        "all_analyst_results": {
            "finnhub": {"success": True, "data": {"buy": 20, "strong_buy": 10, "hold": 8, "sell": 1, "strong_sell": 1}},
            "yfinance": {"success": True, "data": {"buy": 25, "hold": 10, "sell": 3}},
            "seeking_alpha_rapidapi": {"success": False, "data": None, "error": "API key not configured (paid)"},
        },
        "earnings_detail": {
            "beat_count": 4, "miss_count": 0, "surprise_avg": 5.2,
            "quarters": [
                {"period": "Q4 2025", "actual": 2.40, "estimate": 2.35, "surprise_pct": 2.1},
                {"period": "Q3 2025", "actual": 1.46, "estimate": 1.39, "surprise_pct": 5.0},
            ],
        },
        "insider_detail": {"buys_last_50": 3, "sells_last_50": 12, "net_insider_signal": "bearish"},
        "key_articles": [
            {"source": "Seeking Alpha", "title": "Apple's AI Strategy Is Paying Off", "sentiment": 0.32, "sentiment_flag": "🟢", "link": "https://example.com/1"},
            {"source": "Alpha Vantage", "title": "iPhone Sales Disappoint in China", "sentiment": -0.25, "sentiment_flag": "🔴", "link": ""},
            {"source": "Finnhub", "title": "Apple Reports Q4 Earnings Beat", "sentiment": None, "sentiment_flag": "🟡", "link": ""},
        ],
        "data_sources": {
            "price_history": "yfinance",
            "fundamentals": "yfinance",
            "analyst_ratings": "finnhub",
            "insider_trades": "finnhub",
            "news_sentiment": "alpha_vantage",
            "reddit_sentiment": "apewisdom",
            "social_sentiment": "stocktwits",
            "earnings": "finnhub",
            "tradingview": "tradingview-ta",
        },
        "api_status": {
            "price_history": {"success": True, "api_used": "yfinance"},
            "fundamentals": {"success": True, "api_used": "yfinance"},
            "analyst_ratings": {"success": True, "api_used": "finnhub"},
            "insider_trades": {"success": True, "api_used": "finnhub"},
            "news_sentiment": {"success": True, "api_used": "alpha_vantage"},
            "reddit_sentiment": {"success": True, "api_used": "apewisdom"},
            "social_sentiment": {"success": True, "api_used": "stocktwits"},
            "earnings": {"success": True, "api_used": "finnhub"},
            "tradingview": {"success": True, "api_used": "tradingview"},
        },
        "entry_exit": {
            "entries": [
                {"price": 220.0, "method": "SMA50 support"},
                {"price": 210.0, "method": "Fibonacci 38.2%"},
                {"price": 200.0, "method": "SMA200 support"},
            ],
            "exits": [
                {"price": 245.0, "method": "Fibonacci extension"},
                {"price": 260.0, "method": "Upper BB"},
                {"price": 280.0, "method": "All-time high target"},
            ],
            "stop_loss": {"price": 195.0},
            "risk_reward": 2.5,
        },
        "tradingview": {"recommendation": "BUY", "buy_count": 16, "neutral_count": 8, "sell_count": 2},
        "earnings_note": None,
    }

    lines = _format_position_detail(mock_position)
    full_text = "\n".join(lines)

    # Check for expected sections
    expected_sections = [
        ("Header", "### AAPL — Apple Inc."),
        ("Fundamental Score header", "#### Fundamental Score:"),
        ("Fundamental factor table", "| PE Ratio |"),
        ("Technical Score header", "#### Technical Score:"),
        ("Technical indicators", "RSI:"),
        ("Sentiment Score header", "#### Sentiment Score:"),
        ("Sentiment factor table", "| Reddit |"),
        ("Analyst Ratings header", "#### Analyst Ratings"),
        ("Finnhub analyst", "| Finnhub |"),
        ("Seeking Alpha paid note", "Paid key required"),
        ("Earnings header", "#### Earnings"),
        ("Earnings quarter", "Q4 2025"),
        ("Insider header", "#### Insider Trades"),
        ("Entry/Exit header", "#### Entry/Exit Levels"),
        ("Key Articles header", "#### Key Articles"),
        ("Green flag", "🟢"),
        ("Red flag", "🔴"),
        ("Yellow flag", "🟡"),
        ("Data Sources header", "#### Data Sources"),
    ]

    all_ok = True
    for label, expected in expected_sections:
        found = expected in full_text
        status = "✓" if found else "✗"
        if not found:
            all_ok = False
        print(f"  {status} {label}: '{expected}'")

    print(f"\n  Total lines: {len(lines)}")
    print(f"  Result: {'PASS' if all_ok else 'FAIL'} — {sum(1 for _, e in expected_sections if e in full_text)}/{len(expected_sections)} sections found")

    # Print the full output for inspection
    if "--verbose" in sys.argv:
        print("\n" + "=" * 60)
        print("FULL FORMATTED OUTPUT:")
        print("=" * 60)
        for line in lines:
            print(f"  {line}")

    return all_ok


def test_article_sentiment_flags():
    """Test that _collect_articles adds correct sentiment flags."""
    print("\n" + "=" * 60)
    print("TEST 5: Article sentiment flags")
    print("=" * 60)

    from scripts.run_deep_dive import _collect_articles

    news_data = {
        "articles": [
            {"title": "Bullish Article", "source": "Test", "ticker_sentiment": [{"ticker": "AAPL", "ticker_sentiment_score": "0.35"}]},
            {"title": "Neutral Article", "source": "Test", "ticker_sentiment": [{"ticker": "AAPL", "ticker_sentiment_score": "0.05"}]},
            {"title": "Bearish Article", "source": "Test", "ticker_sentiment": [{"ticker": "AAPL", "ticker_sentiment_score": "-0.30"}]},
        ],
        "sentiment_scores": [0.35, 0.05, -0.30],
    }
    rss = [{"title": "RSS No Sentiment", "source": "Seeking Alpha"}]

    articles = _collect_articles("AAPL", news_data, rss)

    all_ok = True
    for a in articles:
        flag = a.get("sentiment_flag", "MISSING")
        sent = a.get("sentiment")
        title = a["title"]
        expected = None
        if "Bullish" in title:
            expected = "🟢"
        elif "Neutral" in title:
            expected = "🟡"
        elif "Bearish" in title:
            expected = "🔴"
        elif "RSS" in title:
            expected = "🟡"  # no AI scoring

        ok = flag == expected if expected else True
        if not ok:
            all_ok = False
        status = "✓" if ok else "✗"
        print(f"  {status} '{title}': flag={flag} sent={sent} (expected={expected})")

    print(f"\n  Result: {'PASS' if all_ok else 'FAIL'}")
    return all_ok


def test_no_data_rating_notes():
    """Test that missing data still produces rating_note (not crashes)."""
    print("\n" + "=" * 60)
    print("TEST 6: No-data rating notes (graceful degradation)")
    print("=" * 60)

    # All None inputs
    result = compute_composite_score(
        fundamentals=None,
        technicals=None,
        tradingview=None,
        reddit=None,
        stocktwits=None,
        news=None,
    )

    fund_factors = result["sub_scores"]["fundamental"]["factors"]
    sent_factors = result["sub_scores"]["sentiment"]["factors"]

    all_ok = True
    for key, f_data in fund_factors.items():
        has_note = "rating_note" in f_data
        if not has_note:
            all_ok = False
        status = "✓" if has_note else "✗"
        print(f"  {status} fundamental.{key}: rating_note={'present' if has_note else 'MISSING'}")

    for key, f_data in sent_factors.items():
        has_note = "rating_note" in f_data
        has_source = "source" in f_data
        if not has_note:
            all_ok = False
        status = "✓" if has_note else "✗"
        print(f"  {status} sentiment.{key}: rating_note={'present' if has_note else 'MISSING'}, source={'present' if has_source else 'MISSING'}")

    print(f"\n  Composite: {result['composite_score']}/10 ({result['rating']}), confidence: {result['confidence']}")
    print(f"  Result: {'PASS' if all_ok else 'FAIL'}")
    return all_ok


def test_scanner_ranking_normalization():
    """
    Test that merge_candidates() normalises counts across sources so that
    StockTwits (10k-50k) doesn't drown out RSS (2-5) and Reddit (10-500).

    Scenario: AAPL appears in RSS (5 mentions) and Reddit (100 mentions).
    GSAT appears ONLY in StockTwits (50,000 watchlist count).
    With the old raw-count ranking GSAT would always win.
    With normalization, AAPL should rank higher because it appears in 2 sources.
    """
    print("\n" + "=" * 60)
    print("TEST 7: Scanner ranking normalization (anti-StockTwits-bias)")
    print("=" * 60)

    from scripts.run_daily_scanner import merge_candidates

    # Simulate realistic source data
    sources = {
        "rss": [
            ("AAPL", 5), ("MSFT", 4), ("GOOGL", 3), ("TSLA", 2),
        ],
        "reddit": [
            ("AAPL", 100), ("GME", 500), ("TSLA", 300), ("NVDA", 50),
        ],
        "stocktwits": [
            ("GSAT", 50000), ("ARKK", 45000), ("NCLH", 39000),
            ("CRSR", 23000), ("SMH", 15000),
        ],
    }

    ranked = merge_candidates(sources)

    # Build a lookup for easy assertions
    ticker_rank = {}
    for i, (ticker, raw, src_count, score, src_list) in enumerate(ranked):
        ticker_rank[ticker] = {
            "rank": i + 1, "raw": raw, "src_count": src_count,
            "score": score, "sources": src_list,
        }

    all_ok = True

    # Test 1: AAPL (2 sources: rss + reddit) should outrank GSAT (1 source: stocktwits)
    aapl = ticker_rank.get("AAPL", {})
    gsat = ticker_rank.get("GSAT", {})
    test1 = aapl.get("rank", 99) < gsat.get("rank", 99)
    status = "✓" if test1 else "✗"
    if not test1:
        all_ok = False
    print(f"  {status} AAPL (2 src, rank {aapl.get('rank')}) beats GSAT (1 src, rank {gsat.get('rank')})")

    # Test 2: TSLA (2 sources: rss + reddit) should outrank single-source stocktwits tickers
    tsla = ticker_rank.get("TSLA", {})
    arkk = ticker_rank.get("ARKK", {})
    test2 = tsla.get("rank", 99) < arkk.get("rank", 99)
    status = "✓" if test2 else "✗"
    if not test2:
        all_ok = False
    print(f"  {status} TSLA (2 src, rank {tsla.get('rank')}) beats ARKK (1 src, rank {arkk.get('rank')})")

    # Test 3: Multi-source tickers should have source_count > 1
    test3 = aapl.get("src_count", 0) == 2 and tsla.get("src_count", 0) == 2
    status = "✓" if test3 else "✗"
    if not test3:
        all_ok = False
    print(f"  {status} AAPL src_count={aapl.get('src_count')}, TSLA src_count={tsla.get('src_count')}")

    # Test 4: GSAT should still appear (not filtered) but ranked lower
    test4 = "GSAT" in ticker_rank
    status = "✓" if test4 else "✗"
    if not test4:
        all_ok = False
    print(f"  {status} GSAT still present (rank {gsat.get('rank')}, score {gsat.get('score')})")

    # Test 5: No single-source ticker should rank #1 when multi-source tickers exist
    top_ticker = ranked[0][0]
    top_sources = ranked[0][2]
    test5 = top_sources >= 2
    status = "✓" if test5 else "✗"
    if not test5:
        all_ok = False
    print(f"  {status} Top-ranked ticker is {top_ticker} with {top_sources} sources")

    # Print full ranking for inspection
    print(f"\n  Full ranking:")
    print(f"  {'Rank':<6} {'Ticker':<8} {'Score':<8} {'Srcs':<6} {'Raw Count':<12} {'Found In'}")
    print(f"  {'─' * 60}")
    for i, (ticker, raw, src_count, score, src_list) in enumerate(ranked):
        print(f"  {i+1:<6} {ticker:<8} {score:<8.0f} {src_count:<6} {raw:<12} {', '.join(src_list)}")

    print(f"\n  Result: {'PASS' if all_ok else 'FAIL'} — 5/5 assertions" if all_ok else f"\n  Result: FAIL")
    return all_ok


def test_quick_score_weight_redistribution():
    """
    Test that compute_quick_score() redistributes weight when a data source
    is missing, and explicitly reports which sources succeeded/failed.

    Scenario A: TradingView fails → fund(50%) + tech(30%) rescaled to 100%
    Scenario B: Only fundamentals available → fund gets 100%
    Scenario C: All sources present → normal 50/30/20 weighting
    """
    print("\n" + "=" * 60)
    print("TEST 8: Quick-score weight redistribution & source tracking")
    print("=" * 60)

    from scripts.scoring import compute_quick_score

    # ── Scenario A: TradingView missing ──
    fund = {"pe_ratio": 15, "revenue_growth": 0.10, "profit_margin": 0.20}
    tech = {"tech_score": 7.0}
    qs_a = compute_quick_score(fundamentals=fund, technicals=tech, tradingview=None)

    test_a1 = "tradingview" in qs_a.get("sources_missing", [])
    test_a2 = "fundamental" in qs_a.get("sources_used", [])
    test_a3 = "technical" in qs_a.get("sources_used", [])
    # Without redistribution this would be: fund_avg*0.5 + 7*0.3 + 5*0.2 = ~5.7
    # With redistribution (50/80 + 30/80): score should be higher because
    # the neutral 5.0 TradingView default is removed
    test_a4 = qs_a["quick_score"] > 5.7  # must be higher than old formula
    status = "✓" if all([test_a1, test_a2, test_a3, test_a4]) else "✗"
    print(f"  {status} TV missing: score={qs_a['quick_score']}, used={qs_a['sources_used']}, missing={qs_a['sources_missing']}")

    all_ok = all([test_a1, test_a2, test_a3, test_a4])

    # ── Scenario B: Only fundamentals (tech + TV both fail) ──
    qs_b = compute_quick_score(fundamentals=fund, technicals=None, tradingview=None)
    test_b1 = set(qs_b.get("sources_missing", [])) == {"technical", "tradingview"}
    test_b2 = qs_b.get("sources_used") == ["fundamental"]
    # Score should equal fund_avg directly (100% weight)
    test_b3 = abs(qs_b["quick_score"] - qs_b["fundamental_avg"]) < 0.01
    status = "✓" if all([test_b1, test_b2, test_b3]) else "✗"
    if not all([test_b1, test_b2, test_b3]):
        all_ok = False
    print(f"  {status} Only fund: score={qs_b['quick_score']} == fund_avg={qs_b['fundamental_avg']}, missing={qs_b['sources_missing']}")

    # ── Scenario C: All sources present ──
    tv = {"recommendation": "BUY"}
    qs_c = compute_quick_score(fundamentals=fund, technicals=tech, tradingview=tv)
    test_c1 = len(qs_c.get("sources_missing", [])) == 0
    test_c2 = len(qs_c.get("sources_used", [])) == 3
    # Normal weighting: fund_avg*0.5 + 7.0*0.3 + 7.5*0.2
    expected_c = round(qs_c["fundamental_avg"] * 0.5 + 7.0 * 0.3 + 7.5 * 0.2, 2)
    test_c3 = abs(qs_c["quick_score"] - expected_c) < 0.01
    status = "✓" if all([test_c1, test_c2, test_c3]) else "✗"
    if not all([test_c1, test_c2, test_c3]):
        all_ok = False
    print(f"  {status} All present: score={qs_c['quick_score']} == expected={expected_c}, missing={qs_c['sources_missing']}")

    # ── Scenario D: All sources fail ──
    qs_d = compute_quick_score(fundamentals=None, technicals=None, tradingview=None)
    test_d1 = len(qs_d.get("sources_missing", [])) == 3
    test_d2 = qs_d["quick_score"] == 5.0
    status = "✓" if all([test_d1, test_d2]) else "✗"
    if not all([test_d1, test_d2]):
        all_ok = False
    print(f"  {status} All fail: score={qs_d['quick_score']} == 5.0, missing={qs_d['sources_missing']}")

    print(f"\n  Result: {'PASS' if all_ok else 'FAIL'}")
    return all_ok


def test_analyst_line_parser():
    """
    Test that _format_analyst_line() correctly parses all three API formats
    into clean, readable one-liners (no raw dict dumps).
    """
    print("\n" + "=" * 60)
    print("TEST 9: Analyst line parser (all 3 sources)")
    print("=" * 60)

    from scripts.run_deep_dive import _format_analyst_line

    all_ok = True

    # ── Finnhub (aggregated buy/hold/sell) ──
    finnhub_data = {"buy": 20, "strong_buy": 5, "hold": 4, "sell": 0, "strong_sell": 1}
    line_fh = _format_analyst_line("finnhub", finnhub_data)
    test_fh = "25 Buy" in line_fh and "4 Hold" in line_fh and "1 Sell" in line_fh and "%" in line_fh
    status = "✓" if test_fh else "✗"
    if not test_fh:
        all_ok = False
    print(f"  {status} Finnhub:        {line_fh}")

    # ── yfinance (modern schema: aggregated recommendation counts, bug #8) ──
    yf_data = {"ticker": "ET", "buy": 23, "hold": 15, "sell": 2,
               "strong_buy": 6, "strong_sell": 1, "period": "0m", "num_analysts": 47}
    line_yf = _format_analyst_line("yfinance", yf_data)
    # buy=23+6=29, hold=15, sell=2+1=3
    test_yf = "29 Buy" in line_yf and "15 Hold" in line_yf and "3 Sell" in line_yf
    # Must NOT contain raw dict characters like "{'ticker'"
    test_yf2 = "{" not in line_yf
    status = "✓" if (test_yf and test_yf2) else "✗"
    if not (test_yf and test_yf2):
        all_ok = False
    print(f"  {status} yfinance:       {line_yf}")

    # ── Seeking Alpha (nested ratings structure) ──
    sa_data = {
        "ticker": "ET",
        "ratings": {
            "data": [{
                "id": "[585868, Tue, 17 Feb 2026]",
                "type": "rating",
                "attributes": {
                    "asDate": "2026-02-17",
                    "ratings": {
                        "authorsRatingStrongBuyCount": 11.0,
                        "authorsRatingBuyCount": 6.0,
                        "authorsRatingHoldCount": 2.0,
                        "authorsRatingSellCount": 2.0,
                        "authorsRatingStrongSellCount": 0.0,
                        "quantRating": 3.304,
                        "sellSideRating": 4.45,
                    },
                },
            }],
        },
    }
    line_sa = _format_analyst_line("seeking_alpha_rapidapi", sa_data)
    test_sa = "17 Buy" in line_sa and "2 Hold" in line_sa and "2 Sell" in line_sa
    test_sa2 = "Quant:" in line_sa and "Wall St:" in line_sa
    test_sa3 = "{" not in line_sa  # no raw dict dump
    status = "✓" if all([test_sa, test_sa2, test_sa3]) else "✗"
    if not all([test_sa, test_sa2, test_sa3]):
        all_ok = False
    print(f"  {status} Seeking Alpha:  {line_sa}")

    # ── yfinance with no counts (edge case: total 0 → clean message) ──
    yf_empty = {"ticker": "ET", "buy": 0, "hold": 0, "sell": 0, "strong_buy": 0, "strong_sell": 0}
    line_yf_e = _format_analyst_line("yfinance", yf_empty)
    test_yfe = "{" not in line_yf_e and "No analyst data" in line_yf_e
    status = "✓" if test_yfe else "✗"
    if not test_yfe:
        all_ok = False
    print(f"  {status} yfinance empty: {line_yf_e}")

    print(f"\n  Result: {'PASS' if all_ok else 'FAIL'}")
    return all_ok


def test_title_sentiment_estimator():
    """Test that title-based sentiment catches bullish/bearish keywords."""
    print("\n" + "=" * 60)
    print("TEST 10: Title-based sentiment estimator")
    print("=" * 60)

    from scripts.run_deep_dive import _estimate_title_sentiment

    all_ok = True
    cases = [
        ("Analyst Upgrades Stock to Outperform", "bullish", lambda s: s is not None and s > 0.15),
        ("Company Beats Earnings, Raises Dividend", "bullish", lambda s: s is not None and s > 0.15),
        ("Stock Downgraded After Disappointing Results", "bearish", lambda s: s is not None and s < -0.15),
        ("Company Warns of Revenue Decline", "bearish", lambda s: s is not None and s < -0.15),
        ("4 Strong High-Yield REITs For Income", "bullish", lambda s: s is not None and s > 0.15),
        ("Market Update February 2026", "neutral", lambda s: s is None),  # no signal
    ]
    for title, expected_dir, check in cases:
        score = _estimate_title_sentiment(title)
        ok = check(score)
        if not ok:
            all_ok = False
        status = "✓" if ok else "✗"
        print(f"  {status} [{expected_dir:>7}] score={score}  \"{title[:55]}\"")

    print(f"\n  Result: {'PASS' if all_ok else 'FAIL'}")
    return all_ok


def test_action_enrichment_with_levels():
    """Test that portfolio actions get enriched with price levels."""
    print("\n" + "=" * 60)
    print("TEST 11: Action enrichment with price levels")
    print("=" * 60)

    from scripts.run_portfolio_review import _enrich_action_with_levels

    ee = {
        "entries": {"aggressive": 55.0, "moderate": 52.0, "conservative": 48.0},
        "targets": {"target_1": 65.0, "target_2": 72.0, "target_3": 80.0},
        "stop_loss": 47.5,
    }
    current = 59.0

    all_ok = True

    # Trailing stop → should include stop price
    a1 = _enrich_action_with_levels("HOLD (consider trailing stop)", ee, current)
    t1 = "$47.50" in a1 and "trailing stop" in a1.lower()
    status = "✓" if t1 else "✗"
    if not t1: all_ok = False
    print(f"  {status} Trailing stop: {a1}")

    # Trim/profit → should include target
    a2 = _enrich_action_with_levels("TRIM (take 50% profit)", ee, current)
    t2 = "$65.00" in a2 and "$47.50" in a2
    status = "✓" if t2 else "✗"
    if not t2: all_ok = False
    print(f"  {status} Trim profit:   {a2}")

    # Buy more → should include entry
    a3 = _enrich_action_with_levels("BUY MORE (avg down — strong fundamentals)", ee, current)
    t3 = "$52.00" in a3
    status = "✓" if t3 else "✗"
    if not t3: all_ok = False
    print(f"  {status} Buy more:      {a3}")

    # Cut loss → should include stop
    a4 = _enrich_action_with_levels("SELL (cut loss)", ee, current)
    t4 = "$47.50" in a4
    status = "✓" if t4 else "✗"
    if not t4: all_ok = False
    print(f"  {status} Cut loss:      {a4}")

    # Plain HOLD → unchanged
    a5 = _enrich_action_with_levels("HOLD", ee, current)
    t5 = a5 == "HOLD"
    status = "✓" if t5 else "✗"
    if not t5: all_ok = False
    print(f"  {status} Plain HOLD:    {a5}")

    print(f"\n  Result: {'PASS' if all_ok else 'FAIL'}")
    return all_ok


if __name__ == "__main__":
    results = []
    results.append(("Fundamental rating_notes", test_fundamental_rating_notes()))
    results.append(("Sentiment rating_notes + sources", test_sentiment_rating_notes_and_sources()))
    results.append(("Composite score structure", test_composite_score_structure()))
    results.append(("Position detail formatter", test_position_detail_formatter()))
    results.append(("Article sentiment flags", test_article_sentiment_flags()))
    results.append(("No-data graceful degradation", test_no_data_rating_notes()))
    results.append(("Scanner ranking normalization", test_scanner_ranking_normalization()))
    results.append(("Quick-score weight redistribution", test_quick_score_weight_redistribution()))
    results.append(("Analyst line parser", test_analyst_line_parser()))
    results.append(("Title sentiment estimator", test_title_sentiment_estimator()))
    results.append(("Action enrichment with levels", test_action_enrichment_with_levels()))

    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    all_pass = True
    for name, passed in results:
        status = "PASS ✓" if passed else "FAIL ✗"
        if not passed:
            all_pass = False
        print(f"  {status}  {name}")

    print(f"\n  Overall: {'ALL TESTS PASSED' if all_pass else 'SOME TESTS FAILED'}")
    print(f"  {sum(1 for _, p in results if p)}/{len(results)} passed")
