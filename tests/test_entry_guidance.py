"""
Unit tests for the actionable entry-guidance layer (ETF proxy + limit price).
"""
import sys, os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from stocks.entry_guidance import (
    recommend_etf, suggest_limit_price, build_entry_guide, liquidity_assessment,
)


class TestRecommendETF:
    def test_ticker_override_wins(self):
        etf, _ = recommend_etf("NVDA", layer="anything", sector="Technology")
        assert etf == "SMH"

    def test_layer_keyword_match(self):
        etf, _ = recommend_etf("RANDOM", layer="💾 Memory & Storage")
        assert etf == "SMH"

    def test_sector_fallback(self):
        etf, _ = recommend_etf("XYZ", sector="Healthcare")
        assert etf == "XLV"

    def test_gem_category_match(self):
        etf, _ = recommend_etf("OKLO", gem_category="Nuclear")
        assert etf == "URA"

    def test_default_when_unknown(self):
        etf, _ = recommend_etf("ZZZZ")
        assert etf == "QQQ"


class TestSuggestLimitPrice:
    def test_near_high_demands_bigger_discount(self):
        near = suggest_limit_price(100.0, -1.0)     # within 1% of high
        off  = suggest_limit_price(100.0, -20.0)    # well off the high
        assert near[1] > off[1]                      # bigger discount when extended
        assert near[0] < off[0]                      # so the limit is lower

    def test_limit_below_current(self):
        limit, disc, _ = suggest_limit_price(50.0, -5.0)
        assert limit < 50.0 and disc > 0

    def test_deep_drawdown_small_discount(self):
        limit, disc, _ = suggest_limit_price(10.0, -60.0)
        assert disc == pytest.approx(0.5)

    def test_returns_note(self):
        _, _, note = suggest_limit_price(100.0, -1.0)
        assert isinstance(note, str) and note


class TestBuildEntryGuide:
    def test_full_guide(self):
        g = build_entry_guide("MU", 120.0, -2.0, layer="💾 Memory & Storage")
        assert g is not None
        assert g.ticker == "MU"
        assert g.etf_ticker == "SMH"
        assert g.limit_price < g.current_price

    def test_missing_price_returns_none(self):
        assert build_entry_guide("MU", 0, -2.0) is None
        assert build_entry_guide("MU", None, -2.0) is None


class TestLiquidity:
    def test_micro_cap_flagged_illiquid(self):
        tier, slip, note = liquidity_assessment(0.3)
        assert tier == "MICRO"
        assert slip >= 1.0

    def test_mega_cap_is_deep(self):
        tier, slip, _ = liquidity_assessment(120.0)
        assert tier == "DEEP"
        assert slip < 0.1

    def test_none_market_cap_is_blank(self):
        tier, slip, note = liquidity_assessment(None)
        assert tier == "" and slip == 0.0

    def test_entry_guide_populates_liquidity_and_warns(self):
        g = build_entry_guide("GFAI", 2.0, -40.0, gem_category="AI-small", market_cap_b=0.2)
        assert g.liquidity_tier == "MICRO"
        assert g.est_slippage_pct >= 1.0
        assert "illiquid" in g.note.lower() or "micro" in g.note.lower()

    def test_large_cap_no_liquidity_warning_in_note(self):
        g = build_entry_guide("NVDA", 120.0, -5.0, layer="compute silicon", market_cap_b=3000.0)
        assert g.liquidity_tier == "DEEP"
