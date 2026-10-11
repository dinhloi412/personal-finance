"""What it is worth: the arithmetic, and the honesty about what is missing.

The fake market prices AAPL at 200 USD, VIC.VN at 100 000 VND, BTC-USD at
50 000 USD and VWCE.DE at 100 EUR; the fake feed trades 200 VND per USD. Every
expected figure below is those numbers combined, nothing more.
"""

from __future__ import annotations

import pytest

from app import models, settings_store, valuation

RATE = 26_000.0  # VND per USD, the fake feed's rate


def cache_quotes(session, *symbols: str):
    """Write the fake market's quotes into the cache.

    The valuation layer reads prices from `price_cache` and never calls the
    market itself, so a test of the arithmetic supplies them directly. The
    numbers are the ones in `conftest.QUOTES`.
    """
    from tests.conftest import QUOTES

    for symbol in symbols or tuple(QUOTES):
        price, currency = QUOTES[symbol]
        session.add(
            models.PriceCache(
                symbol=symbol, price=price, currency=currency, as_of="2026-01-15"
            )
        )
    session.commit()
    return session


@pytest.fixture
def priced(db):
    """A session with every fake quote already cached."""
    return cache_quotes(db)


class TestOnePosition:
    def test_a_dong_position_is_worth_quantity_times_price(self, priced):
        db = priced
        db.add(
            models.Asset(
                symbol="VIC.VN", kind="stock", name="Vingroup",
                quantity=100, cost_basis=9_000_000, currency="VND",
            )
        )
        db.commit()
        asset = valuation.portfolio(db).assets[0]
        assert asset.value == pytest.approx(10_000_000)
        assert asset.value_base == pytest.approx(10_000_000)

    def test_a_dollar_position_is_converted_into_a_dong_base(self, priced):
        db = priced
        db.add(
            models.Asset(
                symbol="AAPL", kind="stock", name="Apple Inc.",
                quantity=10, cost_basis=1_500, currency="USD",
            )
        )
        db.commit()
        asset = valuation.portfolio(db).assets[0]
        # 10 × 200 USD = 2 000 USD, at 200 VND per USD.
        assert asset.value == pytest.approx(2_000)
        assert asset.value_base == pytest.approx(52_000_000)

    def test_the_gain_is_value_minus_cost_in_one_currency(self, priced):
        db = priced
        db.add(
            models.Asset(
                symbol="AAPL", kind="stock", name="Apple Inc.",
                quantity=10, cost_basis=1_500, currency="USD",
            )
        )
        db.commit()
        asset = valuation.portfolio(db).assets[0]
        # (2 000 − 1 500) USD, both sides converted at the same rate.
        assert asset.cost_base == pytest.approx(39_000_000)
        assert asset.gain == pytest.approx(13_000_000)
        assert asset.gain_pct == pytest.approx(100 / 3)

    def test_an_unpriced_position_is_reported_not_valued_at_zero(self, priced):
        db = priced
        db.add(
            models.Asset(
                symbol="NOPE.XX", kind="stock", name="Nothing",
                quantity=5, cost_basis=100, currency="USD",
            )
        )
        db.commit()
        asset = valuation.portfolio(db).assets[0]
        assert asset.value_base is None
        assert asset.reason == valuation.REASON_UNPRICED
        assert valuation.portfolio(db).total == 0.0

    def test_a_position_with_no_cost_has_honest_gaps(self, priced):
        db = priced
        db.add(
            models.Asset(
                symbol="AAPL", kind="stock", name="Apple Inc.",
                quantity=1, cost_basis=None, currency="USD",
            )
        )
        db.commit()
        asset = valuation.portfolio(db).assets[0]
        assert asset.value_base == pytest.approx(5_200_000)
        assert asset.cost_base is None
        assert asset.gain is None
        assert asset.reason == valuation.REASON_NO_COST

    def test_a_quote_in_an_unsupported_currency_is_excluded(self, priced):
        db = priced
        db.add(
            models.Asset(
                symbol="VWCE.DE", kind="fund", name="Vanguard",
                quantity=10, cost_basis=1_000, currency="USD",
            )
        )
        db.commit()
        picture = valuation.portfolio(db)
        asset = picture.assets[0]
        assert asset.value == pytest.approx(1_000)  # in the listing's currency
        assert asset.value_base is None
        assert asset.reason == valuation.REASON_NOT_CONVERTIBLE
        assert picture.total == 0.0
        assert picture.unconverted[0]["reason"] == valuation.REASON_NOT_CONVERTIBLE

    def test_a_position_of_zero_quantity_is_not_a_gain(self, priced):
        db = priced
        db.add(
            models.Asset(
                symbol="AAPL", kind="stock", name="Apple Inc.",
                quantity=0, cost_basis=100, currency="USD",
            )
        )
        db.commit()
        assert valuation.portfolio(db).assets[0].reason == valuation.REASON_NO_QUANTITY


class TestTheTotal:
    def test_one_base_currency_holds_the_whole_portfolio(self, held):
        picture = valuation.portfolio(held)
        # VIC  100 × 100 000 VND               =  10 000 000 VND
        # AAPL  10 ×     200 USD = 2 000 USD   =     400 000 VND
        # cash  50 000 000 VND + 1 000 USD     =  50 200 000 VND
        assert picture.market_value == pytest.approx(62_000_000)
        assert picture.cash_value == pytest.approx(76_000_000)
        assert picture.total == pytest.approx(138_000_000)

    def test_the_total_is_a_sum_of_conversions_not_of_units(self, held):
        picture = valuation.portfolio(held)
        # Adding the 2 000 USD as though it were dong would give 60 202 000.
        assert picture.total != pytest.approx(60_002_000)

    def test_an_unconvertible_position_stays_out_of_the_total(self, held):
        held.add(
            models.Asset(
                symbol="VWCE.DE", kind="fund", name="Vanguard",
                quantity=10, cost_basis=1_000, currency="USD",
            )
        )
        held.commit()
        cache_quotes(held, "VWCE.DE")
        picture = valuation.portfolio(held)
        assert picture.total == pytest.approx(138_000_000)
        assert len(picture.unconverted) == 1
        assert picture.unconverted[0]["label"].startswith("VWCE.DE")

    def test_the_gain_ignores_cash(self, held):
        picture = valuation.portfolio(held)
        # Cost: AAPL 1 500 USD = 300 000 VND + VIC 9 000 000 VND.
        assert picture.cost_base == pytest.approx(48_000_000)
        assert picture.gain == pytest.approx(62_000_000 - 48_000_000)

    def test_a_portfolio_level_gain_is_withheld_if_a_counted_position_has_no_cost(self, held):
        held.add(
            models.Asset(
                symbol="BTC-USD", kind="crypto", name="Bitcoin",
                quantity=1, cost_basis=None, currency="USD",
            )
        )
        held.commit()
        cache_quotes(held, "BTC-USD")
        picture = valuation.portfolio(held)
        # The position IS in the total; only the gain is withheld, because a
        # gain over a cost that is not known is not a gain.
        assert picture.total == pytest.approx(138_000_000 + 50_000 * RATE)
        assert picture.gain is None
        assert picture.gain_pct is None

    def test_every_kind_is_reported_even_when_it_is_empty(self, held):
        kinds = [row["kind"] for row in valuation.portfolio(held).by_kind]
        assert kinds == ["stock", "fund", "crypto", "cash"]

    def test_cash_in_two_currencies_lands_in_one_total(self, held):
        by_kind = {row["kind"]: row for row in valuation.portfolio(held).by_kind}
        assert by_kind["cash"]["value"] == pytest.approx(76_000_000)
        assert by_kind["cash"]["count"] == 2

    def test_exposure_is_reported_per_currency_in_both_units(self, held):
        rows = {row["currency"]: row for row in valuation.portfolio(held).by_currency}
        # 50 000 000 VND of cash + 10 000 000 VND of VIC.
        assert rows["VND"]["amount"] == pytest.approx(60_000_000)
        # 2 000 USD of AAPL + 1 000 USD of cash.
        assert rows["USD"]["amount"] == pytest.approx(3_000)
        # Only the converted column may be compared between the two rows.
        assert rows["USD"]["value_base"] == pytest.approx(78_000_000)


class TestChangingTheBase:
    def test_the_same_portfolio_reads_in_the_other_currency(self, held):
        in_vnd = valuation.portfolio(held, base="VND").total
        in_usd = valuation.portfolio(held, base="USD").total
        assert in_vnd == pytest.approx(138_000_000)
        assert in_usd == pytest.approx(138_000_000 / RATE)

    def test_the_response_says_which_rates_it_used(self, held):
        picture = valuation.portfolio(held)
        assert [row["currency"] for row in picture.rates] == ["USD"]
        assert picture.rates[0]["as_of"]


class TestHistory:
    def test_a_snapshot_records_the_total_of_its_day(self, held):
        row = valuation.write_snapshot(held)
        assert row.total == pytest.approx(138_000_000)
        assert row.base_currency == "VND"
        assert row.as_of == models.today_iso()

    def test_two_snapshots_on_one_day_are_one_point(self, held):
        valuation.write_snapshot(held)
        valuation.write_snapshot(held)
        assert len(valuation.history(held)) == 1

    def test_each_point_remembers_the_base_it_was_written_in(self, held):
        valuation.write_snapshot(held, day="2026-01-01")  # VND
        settings_store.set_base_currency(held, "USD")
        valuation.write_snapshot(held, day="2026-01-02")

        points = valuation.history(held)
        assert [point["base_currency"] for point in points] == ["VND", "USD"]
        # The first point is untouched by the change of base.
        assert points[0]["total"] == pytest.approx(138_000_000)

    def test_history_is_oldest_first(self, held):
        valuation.write_snapshot(held, day="2026-01-01")
        valuation.write_snapshot(held, day="2026-01-03")
        valuation.write_snapshot(held, day="2026-01-02")
        assert [point["as_of"] for point in valuation.history(held)] == [
            "2026-01-01",
            "2026-01-02",
            "2026-01-03",
        ]
