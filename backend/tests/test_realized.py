"""Selling a position: what leaves, what it cost, and what is kept behind.

The arithmetic here is deliberately checkable by hand. A position of 100 units
that cost 9 000 000 ₫ gives up 3 600 000 ₫ of that cost when 40 of them are
sold, and its own cost basis falls to 5 400 000 ₫ — one subtraction and one
multiplication, both visible in the test.

The fake feed trades 26 000 VND per USD (`conftest.FEED_FROM_USD`), which is
what the dollar figures below use.
"""

from __future__ import annotations

import pytest

from app import models, realized, valuation

RATE = 26_000.0  # VND per USD, the fake feed's rate


def cache_quotes(session, *symbols: str):
    """Write the fake market's quotes into the cache, as `test_valuation` does."""
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


def hold(db, **overrides) -> models.Asset:
    """One dong position: 100 units that cost 9 000 000 ₫, quoted at 100 000 ₫.

    Worth 10 000 000 ₫, so a sale at the quoted price is a gain and a sale below
    it is a loss, and neither needs a calculator.
    """
    fields = {
        "symbol": "VIC.VN",
        "kind": "stock",
        "name": "Vingroup JSC",
        "quantity": 100.0,
        "cost_basis": 9_000_000.0,
        "currency": "VND",
    }
    fields.update(overrides)
    asset = models.Asset(**fields)
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


class TestProportionalCost:
    """The one decision this feature cannot avoid making."""

    def test_selling_part_of_a_position_releases_part_of_its_cost(self):
        assert realized.proportional_cost(9_000_000.0, sold=40, held=100) == pytest.approx(
            3_600_000.0
        )

    def test_selling_all_of_it_releases_exactly_what_was_paid(self):
        # Not 9 000 000 × 1.0: the number the user typed leaves unchanged.
        assert realized.proportional_cost(9_000_000.0, sold=100, held=100) == 9_000_000.0

    def test_a_position_with_no_recorded_cost_releases_none(self):
        """The gap has to stay a gap. Deriving a cost from today's price is the
        "movement since I wrote it down" this app refuses to call profit."""
        assert realized.proportional_cost(None, sold=40, held=100) is None

    def test_a_fractional_position_is_divided_not_rounded(self):
        # 525.87 fund units, a third of them sold.
        assert realized.proportional_cost(
            10_000_000.0, sold=175.29, held=525.87
        ) == pytest.approx(3_333_333.33, rel=1e-9)


class TestApplySale:
    def test_a_partial_sale_shrinks_the_position_and_its_cost(self, priced):
        db = priced
        asset = hold(db)

        realized.apply_sale(
            db,
            asset,
            quantity=40,
            proceeds=4_000_000.0,
            proceeds_currency="VND",
            sold_on="2026-02-01",
        )
        db.commit()

        db.refresh(asset)
        assert asset.quantity == pytest.approx(60.0)
        assert asset.cost_basis == pytest.approx(5_400_000.0)

    def test_a_full_sale_removes_the_position(self, priced):
        db = priced
        asset = hold(db)

        realized.apply_sale(
            db,
            asset,
            quantity=100,
            proceeds=12_000_000.0,
            proceeds_currency="VND",
            sold_on="2026-02-01",
        )
        db.commit()

        assert db.query(models.Asset).count() == 0
        assert db.query(models.Realized).count() == 1

    def test_a_full_sale_leaves_no_ghost_in_the_unconverted_list(self, priced):
        """A position kept at zero would have no value and would be reported on
        the dashboard as "not counted, khối lượng bằng 0" — a warning about a
        position the user has already sold."""
        db = priced
        asset = hold(db)
        realized.apply_sale(
            db,
            asset,
            quantity=100,
            proceeds=12_000_000.0,
            proceeds_currency="VND",
            sold_on="2026-02-01",
        )
        db.commit()

        picture = valuation.portfolio(db)
        assert picture.assets == []
        assert picture.unconverted == []

    def test_the_sale_keeps_the_facts_of_the_trade(self, priced):
        db = priced
        asset = hold(db)
        row = realized.apply_sale(
            db,
            asset,
            quantity=25,
            proceeds=2_000_000.0,
            proceeds_currency="VND",
            sold_on="2026-02-01",
            note="bán một phần",
        )
        db.commit()

        assert (row.symbol, row.kind, row.name) == ("VIC.VN", "stock", "Vingroup JSC")
        assert row.quantity == pytest.approx(25.0)
        assert row.currency == "VND"
        assert row.cost_removed == pytest.approx(2_250_000.0)
        assert row.proceeds == pytest.approx(2_000_000.0)
        assert row.proceeds_currency == "VND"
        assert row.sold_on == "2026-02-01"
        assert row.note == "bán một phần"

    def test_the_facts_survive_the_position_being_deleted(self, priced):
        """The record is self-contained on purpose: it carries its own symbol
        and name rather than pointing at a registry row for live quotes."""
        db = priced
        asset = hold(db)
        realized.apply_sale(
            db,
            asset,
            quantity=100,
            proceeds=12_000_000.0,
            proceeds_currency="VND",
            sold_on="2026-02-01",
        )
        db.commit()

        sale = valuation.portfolio(db).realized[0]
        assert sale.symbol == "VIC.VN"
        assert sale.name == "Vingroup JSC"

    def test_selling_more_than_is_held_changes_nothing(self, priced):
        db = priced
        asset = hold(db)
        with pytest.raises(ValueError, match="only 100"):
            realized.apply_sale(
                db,
                asset,
                quantity=101,
                proceeds=1.0,
                proceeds_currency="VND",
                sold_on="2026-02-01",
            )
        db.rollback()
        assert db.query(models.Asset).count() == 1
        assert db.query(models.Realized).count() == 0

    def test_selling_nothing_is_refused(self, priced):
        db = priced
        asset = hold(db)
        with pytest.raises(ValueError, match="more than zero"):
            realized.apply_sale(
                db,
                asset,
                quantity=0,
                proceeds=1.0,
                proceeds_currency="VND",
                sold_on="2026-02-01",
            )

    def test_a_position_already_at_zero_cannot_be_sold(self, priced):
        db = priced
        asset = hold(db, quantity=0)
        with pytest.raises(ValueError, match="nothing left to sell"):
            realized.apply_sale(
                db,
                asset,
                quantity=1,
                proceeds=1.0,
                proceeds_currency="VND",
                sold_on="2026-02-01",
            )

    def test_float_dust_left_by_a_full_sale_is_not_a_position(self, priced):
        """`quantity` arrives from a form pre-filled with what is held, so it is
        the same float — but a subtraction of two floats is entitled to leave a
        remainder, and a position of 1e-15 units must not survive as a row."""
        db = priced
        asset = hold(db, quantity=100.0)
        realized.apply_sale(
            db,
            asset,
            quantity=100.0 - 1e-14,
            proceeds=10_000_000.0,
            proceeds_currency="VND",
            sold_on="2026-02-01",
        )
        db.commit()

        assert db.query(models.Asset).count() == 0
        # And the whole cost went with it: no cost basis left on a position that
        # no longer exists, and none of it counted twice.
        assert db.query(models.Realized).one().cost_removed == pytest.approx(9_000_000.0)


class TestRealisedGain:
    def test_the_gain_is_what_came_back_minus_the_cost_it_released(self, priced):
        db = priced
        asset = hold(db)
        realized.apply_sale(
            db,
            asset,
            quantity=100,
            proceeds=12_000_000.0,
            proceeds_currency="VND",
            sold_on="2026-02-01",
        )
        db.commit()

        sale = valuation.portfolio(db).realized[0]
        assert sale.proceeds_base == pytest.approx(12_000_000.0)
        assert sale.cost_base == pytest.approx(9_000_000.0)
        assert sale.gain == pytest.approx(3_000_000.0)
        assert sale.gain_pct == pytest.approx(100 / 3)
        assert sale.reason is None

    def test_a_loss_is_a_negative_gain_not_a_missing_one(self, priced):
        db = priced
        asset = hold(db)
        realized.apply_sale(
            db,
            asset,
            quantity=100,
            proceeds=7_000_000.0,
            proceeds_currency="VND",
            sold_on="2026-02-01",
        )
        db.commit()

        sale = valuation.portfolio(db).realized[0]
        assert sale.gain == pytest.approx(-2_000_000.0)
        assert sale.gain_pct == pytest.approx(-200 / 9)

    def test_a_sale_with_no_recorded_cost_has_an_unknown_gain(self, priced):
        db = priced
        asset = hold(db, cost_basis=None)
        realized.apply_sale(
            db,
            asset,
            quantity=100,
            proceeds=12_000_000.0,
            proceeds_currency="VND",
            sold_on="2026-02-01",
        )
        db.commit()

        sale = valuation.portfolio(db).realized[0]
        assert sale.cost_base is None
        assert sale.gain is None
        assert sale.reason == valuation.REASON_NO_COST
        # What DID come back is still known and still shown.
        assert sale.proceeds_base == pytest.approx(12_000_000.0)

    def test_both_sides_of_a_dollar_sale_are_converted_from_their_own_currency(self, priced):
        """What you received is in the market's currency, what you paid is in
        your account's. Each is converted once, from its own."""
        db = priced
        asset = hold(
            db,
            symbol="AAPL",
            name="Apple Inc.",
            quantity=10,
            cost_basis=1_500.0,  # USD
            currency="USD",
        )
        realized.apply_sale(
            db,
            asset,
            quantity=5,
            proceeds=1_100.0,  # USD, half the position sold at 220
            proceeds_currency="USD",
            sold_on="2026-02-01",
        )
        db.commit()

        sale = valuation.portfolio(db).realized[0]
        assert sale.proceeds_base == pytest.approx(1_100 * RATE)
        assert sale.cost_base == pytest.approx(750 * RATE)
        assert sale.gain == pytest.approx(350 * RATE)

    def test_the_gain_is_never_read_off_the_current_price(self, priced):
        """A position sold at 8 000 000 ₫ while the market now says 10 000 000 ₫
        made a loss, and the loss is what gets recorded. Using the current price
        would report a profit on a trade that lost money."""
        db = priced
        asset = hold(db)
        realized.apply_sale(
            db,
            asset,
            quantity=100,
            proceeds=8_000_000.0,
            proceeds_currency="VND",
            sold_on="2026-02-01",
        )
        db.commit()

        picture = valuation.portfolio(db)
        assert picture.realized[0].gain == pytest.approx(-1_000_000.0)
        # The position is gone, so nothing claims that 10 000 000 ₫ any more.
        assert picture.market_value == 0.0


class TestTheDashboardTotals:
    def test_no_sales_means_zero_realised_and_a_total_equal_to_the_unrealised(self, priced):
        db = priced
        hold(db)
        picture = valuation.portfolio(db)

        assert picture.realized == []
        assert picture.realized_count == 0
        assert picture.realized_gain == 0.0
        assert picture.gain == pytest.approx(1_000_000.0)
        assert picture.total_gain == pytest.approx(1_000_000.0)
        assert picture.total_gain_pct == pytest.approx(picture.gain_pct)

    def test_the_total_is_both_sides_added(self, priced):
        """Half of a position sold at a profit, and the other half still held
        below what it cost: 2 000 000 ₫ realised against 500 000 ₫ unrealised."""
        db = priced
        asset = hold(db)
        realized.apply_sale(
            db,
            asset,
            quantity=50,
            proceeds=6_500_000.0,  # 4 500 000 cost released → +2 000 000
            proceeds_currency="VND",
            sold_on="2026-02-01",
        )
        db.commit()

        # What is left: 50 units worth 5 000 000 ₫ against 4 500 000 ₫ of cost.
        picture = valuation.portfolio(db)
        assert picture.gain == pytest.approx(500_000.0)
        assert picture.realized_gain == pytest.approx(2_000_000.0)
        assert picture.total_gain == pytest.approx(2_500_000.0)
        # 2 500 000 over the 9 000 000 committed in total.
        assert picture.total_gain_pct == pytest.approx(2_500_000 / 9_000_000 * 100)

    def test_a_fully_sold_portfolio_reports_its_gain_rather_than_an_unknown(self, priced):
        """The state this whole feature exists for. The unrealised figure is
        None by long-standing rule (nothing held), and the total must not
        inherit that: the money was made."""
        db = priced
        asset = hold(db)
        realized.apply_sale(
            db,
            asset,
            quantity=100,
            proceeds=12_000_000.0,
            proceeds_currency="VND",
            sold_on="2026-02-01",
        )
        db.commit()

        picture = valuation.portfolio(db)
        assert picture.assets == []
        assert picture.gain is None
        assert picture.realized_gain == pytest.approx(3_000_000.0)
        assert picture.total_gain == pytest.approx(3_000_000.0)
        assert picture.total_gain_pct == pytest.approx(100 / 3)

    def test_one_sale_without_a_cost_makes_both_totals_unknown(self, priced):
        """The rule the unrealised figure already follows: a total that would be
        too large is not printed. Here it would count the whole 12 000 000 ₫ as
        profit."""
        db = priced
        asset = hold(db, cost_basis=None)
        realized.apply_sale(
            db,
            asset,
            quantity=100,
            proceeds=12_000_000.0,
            proceeds_currency="VND",
            sold_on="2026-02-01",
        )
        db.commit()

        picture = valuation.portfolio(db)
        assert picture.realized_cost_base is None
        assert picture.realized_gain is None
        assert picture.total_gain is None
        assert picture.total_gain_pct is None

    def test_the_sales_are_listed_newest_first(self, priced):
        db = priced
        asset = hold(db)
        for index, day in enumerate(["2026-01-05", "2026-03-09", "2026-02-01"]):
            realized.apply_sale(
                db,
                asset,
                quantity=10,
                proceeds=1_000_000.0,
                proceeds_currency="VND",
                sold_on=day,
            )
        db.commit()

        assert [sale.sold_on for sale in valuation.portfolio(db).realized] == [
            "2026-03-09",
            "2026-02-01",
            "2026-01-05",
        ]

    def test_realised_gain_is_not_market_value(self, priced):
        """A sale is money that already came back, so it is not part of what is
        held — the total assets must not grow when a position is sold."""
        db = priced
        asset = hold(db)
        before = valuation.portfolio(db).total
        realized.apply_sale(
            db,
            asset,
            quantity=100,
            proceeds=12_000_000.0,
            proceeds_currency="VND",
            sold_on="2026-02-01",
        )
        db.commit()

        assert before == pytest.approx(10_000_000.0)
        assert valuation.portfolio(db).total == 0.0


class TestSellingOverHttp:
    """The endpoint, and the two things it refuses to guess."""

    def make(self, client, **overrides):
        body = {
            "symbol": "VIC.VN",
            "kind": "stock",
            "quantity": 100,
            "cost_basis": 9_000_000,
            "currency": "VND",
        }
        body.update(overrides)
        response = client.post("/api/assets", json=body)
        assert response.status_code == 201, response.text
        return response.json()

    def test_a_sale_answers_with_the_gain_it_locked_in(self, client):
        asset = self.make(client)
        response = client.post(
            f"/api/assets/{asset['id']}/sell",
            json={"quantity": 100, "proceeds": 12_000_000, "sold_on": "2026-02-01"},
        )
        assert response.status_code == 200, response.text
        sale = response.json()
        assert sale["symbol"] == "VIC.VN"
        assert sale["cost_removed"] == pytest.approx(9_000_000)
        assert sale["gain"] == pytest.approx(3_000_000)
        assert sale["sold_on"] == "2026-02-01"

    def test_the_proceeds_are_recorded_in_the_markets_currency(self, client):
        """AAPL is quoted in USD, so what came back for it is dollars — the
        position's own currency is asked for only when nothing was ever quoted."""
        asset = self.make(
            client,
            symbol="AAPL",
            kind="stock",
            name="Apple Inc.",
            quantity=10,
            cost_basis=1_500,
            currency="USD",
        )
        response = client.post(
            f"/api/assets/{asset['id']}/sell",
            json={"quantity": 10, "proceeds": 2_000},
        )
        assert response.status_code == 200, response.text
        sale = response.json()
        assert sale["proceeds_currency"] == "USD"
        assert sale["proceeds"] == pytest.approx(2_000)
        assert sale["proceeds_base"] == pytest.approx(2_000 * RATE)

    def test_the_position_disappears_when_it_is_all_sold(self, client):
        asset = self.make(client)
        client.post(
            f"/api/assets/{asset['id']}/sell",
            json={"quantity": 100, "proceeds": 12_000_000},
        )
        assert client.get("/api/assets").json() == []

    def test_selling_more_than_is_held_is_refused_with_a_reason(self, client):
        asset = self.make(client)
        response = client.post(
            f"/api/assets/{asset['id']}/sell",
            json={"quantity": 101, "proceeds": 12_000_000},
        )
        # 422, not 400: a refused value is the request's fault, which is what
        # `deps.refused` means everywhere else in this API.
        assert response.status_code == 422
        assert "only 100" in response.json()["detail"]
        assert client.get("/api/assets").json()[0]["quantity"] == pytest.approx(100)

    def test_a_quantity_of_zero_is_refused_by_the_schema(self, client):
        asset = self.make(client)
        response = client.post(
            f"/api/assets/{asset['id']}/sell",
            json={"quantity": 0, "proceeds": 1},
        )
        assert response.status_code == 422

    def test_selling_a_position_that_does_not_exist_is_a_404(self, client):
        assert (
            client.post(
                "/api/assets/999/sell", json={"quantity": 1, "proceeds": 1}
            ).status_code
            == 404
        )

    def test_the_sale_is_recorded_under_todays_date_by_default(self, client):
        asset = self.make(client)
        sale = client.post(
            f"/api/assets/{asset['id']}/sell",
            json={"quantity": 10, "proceeds": 1_000_000},
        ).json()
        assert sale["sold_on"] == models.today_iso()

    def test_the_sale_appears_in_the_portfolio_and_in_its_own_list(self, client):
        asset = self.make(client)
        client.post(
            f"/api/assets/{asset['id']}/sell",
            json={"quantity": 100, "proceeds": 12_000_000, "sold_on": "2026-02-01"},
        )

        portfolio = client.get("/api/portfolio").json()
        assert portfolio["realized_count"] == 1
        assert portfolio["realized_gain"] == pytest.approx(3_000_000)
        assert portfolio["total_gain"] == pytest.approx(3_000_000)
        assert portfolio["realized"][0]["symbol"] == "VIC.VN"
        assert [row["symbol"] for row in client.get("/api/realized").json()] == ["VIC.VN"]

    def test_a_sale_can_be_deleted_without_resurrecting_the_position(self, client):
        asset = self.make(client)
        sale = client.post(
            f"/api/assets/{asset['id']}/sell",
            json={"quantity": 100, "proceeds": 12_000_000, "sold_on": "2026-02-01"},
        ).json()

        assert client.delete(f"/api/realized/{sale['id']}").status_code == 204
        assert client.get("/api/realized").json() == []
        assert client.get("/api/assets").json() == []
        # And the dashboard goes back to knowing nothing about a gain, rather
        # than to claiming the one that was just deleted.
        assert client.get("/api/portfolio").json()["total_gain"] == 0.0

    def test_deleting_a_sale_that_does_not_exist_is_a_404(self, client):
        assert client.delete("/api/realized/999").status_code == 404

    def test_a_partial_sale_leaves_the_rest_of_the_position_valued(self, client):
        asset = self.make(client)
        client.post(
            f"/api/assets/{asset['id']}/sell",
            json={"quantity": 40, "proceeds": 5_200_000, "sold_on": "2026-02-01"},
        )

        position = client.get("/api/assets").json()[0]
        assert position["quantity"] == pytest.approx(60)
        assert position["cost_basis"] == pytest.approx(5_400_000)
        # 60 units at the fake market's 100 000 ₫, against 5 400 000 ₫ of cost.
        assert position["value_base"] == pytest.approx(6_000_000)
        assert position["gain"] == pytest.approx(600_000)

    def test_the_money_does_not_appear_as_cash_on_its_own(self, client):
        """Selling records a sale, not a deposit. With the cash link off — the
        default — the proceeds do not reach a balance the user never named."""
        self.make(client)
        asset = client.get("/api/assets").json()[0]
        client.post(
            f"/api/assets/{asset['id']}/sell",
            json={"quantity": 100, "proceeds": 12_000_000},
        )
        assert [row["balance"] for row in client.get("/api/cash").json()] == [0.0, 0.0]
        assert client.get("/api/portfolio").json()["cash_value"] == 0.0

    def test_a_position_quoted_in_a_third_currency_can_still_be_sold(self, client):
        """`VWCE.DE` is quoted in EUR, which this app deliberately cannot
        convert — and holding one is allowed, the price is simply reported and
        left out of the total. Answering its sale with a refusal would leave the
        user holding a position they no longer own, so the sale is recorded and
        the gap is reported instead: nothing is claimed to be profit."""
        asset = self.make(
            client,
            symbol="VWCE.DE",
            kind="fund",
            name="Vanguard FTSE All-World",
            quantity=10,
            cost_basis=900,
            currency="USD",
        )
        response = client.post(
            f"/api/assets/{asset['id']}/sell",
            json={"quantity": 10, "proceeds": 1_100},
        )
        assert response.status_code == 200, response.text
        sale = response.json()
        assert sale["proceeds_currency"] == "EUR"
        assert sale["proceeds"] == pytest.approx(1_100)
        # The cost was in dollars, so that side is known and stays known.
        assert sale["cost_base"] == pytest.approx(900 * RATE)
        # The proceeds are not, so the gain is absent rather than invented.
        assert sale["proceeds_base"] is None
        assert sale["gain"] is None
        assert sale["reason"] == "not_convertible"
        # And the portfolio says it does not know, instead of counting the
        # 1 100 EUR as pure profit.
        portfolio = client.get("/api/portfolio").json()
        assert portfolio["realized_gain"] is None
        assert portfolio["total_gain"] is None
        # The sale is still on the record, and the position is still gone.
        assert client.get("/api/realized").json()[0]["symbol"] == "VWCE.DE"
        assert client.get("/api/assets").json() == []
