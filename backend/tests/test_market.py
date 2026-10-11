"""What the market module must get right, away from the network.

The fake quotes come from `conftest.QUOTES`, so the expected numbers below are
the same numbers a reader can see in that table.
"""

from __future__ import annotations

import pytest

from app import market


class TestIdentity:
    """A symbol is not a name, and the module has to be able to tell them apart."""

    def test_a_vietnamese_suffix_means_dong(self):
        assert market.currency_from_symbol("VIC.VN") == "VND"
        assert market.currency_from_symbol("FPT.VN") == "VND"

    def test_a_bare_ticker_means_dollars(self):
        assert market.currency_from_symbol("AAPL") == "USD"

    def test_a_crypto_pair_means_dollars(self):
        assert market.currency_from_symbol("BTC-USD") == "USD"

    def test_a_bare_crypto_ticker_is_completed_to_a_pair(self):
        assert market.normalise_symbol("btc", kind="crypto") == "BTC-USD"

    def test_a_completed_pair_is_left_alone(self):
        assert market.normalise_symbol("btc-eur", kind="crypto") == "BTC-EUR"

    def test_a_stock_is_never_given_a_crypto_suffix(self):
        assert market.normalise_symbol("aapl", kind="stock") == "AAPL"

    def test_an_index_is_not_something_this_app_tracks(self):
        # An index cannot be held, so it must never reach a portfolio.
        assert market.kind_from_quote_type("INDEX") is None

    def test_the_tracked_kinds_are_mapped(self):
        assert market.kind_from_quote_type("EQUITY") == "stock"
        assert market.kind_from_quote_type("ETF") == "fund"
        assert market.kind_from_quote_type("MUTUALFUND") == "fund"
        assert market.kind_from_quote_type("CRYPTOCURRENCY") == "crypto"


class TestSearch:
    def test_a_hit_this_app_cannot_hold_is_dropped(self):
        hits = market.search("a")
        symbols = [hit.symbol for hit in hits]
        assert "^GSPC" not in symbols
        assert "AAPL" in symbols

    def test_an_empty_query_asks_the_feed_nothing(self):
        assert market.search("   ") == []

    def test_a_resolved_symbol_carries_its_currency(self):
        hit = market.lookup_symbol("VIC.VN")
        assert hit is not None
        assert hit.currency == "VND"

    def test_a_symbol_the_market_does_not_know_resolves_to_nothing(self):
        assert market.lookup_symbol("NOPE.XX") is None


class TestQuote:
    def test_a_quote_carries_the_close_and_the_session(self):
        priced = market.quote("AAPL")
        assert priced.price == 200.0
        assert priced.currency == "USD"
        assert priced.as_of == "2026-01-15"

    def test_an_unknown_symbol_raises_rather_than_returning_zero(self):
        # A zero price would silently make a position worth nothing.
        with pytest.raises(market.MarketError):
            market.quote("NOPE.XX")
