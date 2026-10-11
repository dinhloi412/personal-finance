"""Money moving between cash and a holding: the link, and everything it moves.

Cash is **one pot per currency** (`app.cash`), so most of this file is about the
pot a trade belongs to and the figure that moves. The fake feed trades 26 000
VND per USD, a position of 100 units bought for 9 000 000 ₫ is worth 10 000 000 ₫
at the fake market's 100 000 ₫, and a pot starts from a round balance so a
subtraction is visible.

The tests are grouped by the promise each one keeps, because the failure mode
this feature has is not an exception — it is a balance that quietly stops
matching the money it is supposed to represent.
"""

from __future__ import annotations

import pytest

from app import cash, models, movements

RATE = 26_000.0  # VND per USD, the fake feed's rate


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def linked(client, on: bool = True):
    """Turn the cash link on or off over HTTP, the way the interface does."""
    response = client.patch("/api/settings", json={"cash_linked": on})
    assert response.status_code == 200, response.text
    assert response.json()["cash_linked"] is on


def pot(client, currency: str = "VND") -> dict:
    """One of the two pots, by currency."""
    rows = client.get("/api/cash").json()
    return next(row for row in rows if row["currency"] == currency)


def fill(client, currency: str = "VND", balance: float = 50_000_000.0) -> dict:
    """Put money in a pot — the only way cash is created now."""
    return client.patch(
        f"/api/cash/{pot(client, currency)['id']}", json={"balance": balance}
    ).json()


def balance_of(client, currency: str = "VND") -> float:
    return pot(client, currency)["balance"]


def position(client, symbol="VIC.VN", quantity=100, cost=9_000_000, currency="VND") -> dict:
    response = client.post(
        "/api/assets",
        json={
            "symbol": symbol,
            "kind": "stock",
            "name": symbol,
            "quantity": quantity,
            "cost_basis": cost,
            "currency": currency,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def movements_of(client) -> list[dict]:
    """Every movement, newest first."""
    return client.get("/api/portfolio").json()["movements"]


def trades(client) -> list[dict]:
    """Only the movements a *trade* caused.

    Typing a balance writes a line of its own (`TestTheBooksBalance`), and the
    setup in this file uses that path — so a test about what a purchase does
    reads this, not the whole list.
    """
    return [row for row in movements_of(client) if row["subject"] != "cash"]


# --------------------------------------------------------------------------
# The switch
# --------------------------------------------------------------------------


class TestTheSwitch:
    def test_it_is_off_until_the_user_turns_it_on(self, client):
        """The whole initial-entry story depends on this: while a portfolio is
        being typed in, cash and holdings are two independent facts."""
        assert client.get("/api/settings").json()["cash_linked"] is False

    def test_it_can_be_turned_on_and_off(self, client):
        linked(client, True)
        assert client.get("/api/settings").json()["cash_linked"] is True
        linked(client, False)
        assert client.get("/api/settings").json()["cash_linked"] is False

    def test_off_means_nothing_moves(self, client):
        fill(client, "VND", 50_000_000)
        created = position(client)
        assert created["cash"]["moved"] is False
        assert created["cash"]["skipped"] == "link_off"
        assert balance_of(client) == 50_000_000
        # Nothing but the line that typing the balance wrote.
        assert trades(client) == []

    def test_a_link_turned_on_later_does_not_rewrite_the_past(self, client):
        fill(client, "VND", 50_000_000)
        position(client)  # bought while off
        linked(client, True)
        assert balance_of(client) == 50_000_000
        assert trades(client) == []


# --------------------------------------------------------------------------
# Which pot a trade belongs to
# --------------------------------------------------------------------------


class TestThePot:
    """The pot is the trade's own currency. There is nothing to choose."""

    def test_a_dong_trade_moves_the_dong_pot(self, client):
        linked(client)
        fill(client, "VND", 50_000_000)
        fill(client, "USD", 1_000)

        created = position(client, cost=9_000_000)
        assert created["cash"]["currency"] == "VND"
        assert balance_of(client, "VND") == pytest.approx(41_000_000)
        assert balance_of(client, "USD") == 1_000

    def test_a_dollar_trade_moves_the_dollar_pot(self, client):
        """And moves it in dollars: the amount is the trade's own number, with
        no rate and no rounding, because the pot is already in that currency."""
        linked(client)
        fill(client, "VND", 50_000_000)
        fill(client, "USD", 5_000)

        created = position(client, symbol="AAPL", quantity=10, cost=1_500, currency="USD")
        assert created["cash"]["currency"] == "USD"
        assert created["cash"]["amount"] == pytest.approx(-1_500)
        assert balance_of(client, "USD") == pytest.approx(3_500)
        assert balance_of(client, "VND") == 50_000_000
        assert movements_of(client)[0]["rate"] is None

    def test_both_pots_exist_without_being_asked_for(self, client):
        assert [row["currency"] for row in client.get("/api/cash").json()] == [
            "VND",
            "USD",
        ]


# --------------------------------------------------------------------------
# Buying
# --------------------------------------------------------------------------


class TestBuying:
    def test_a_purchase_leaves_the_pot(self, client):
        linked(client)
        fill(client, "VND", 50_000_000)
        created = position(client)

        assert created["cash"]["moved"] is True
        assert created["cash"]["amount"] == pytest.approx(-9_000_000)
        assert created["cash"]["balance"] == pytest.approx(41_000_000)
        assert balance_of(client) == pytest.approx(41_000_000)

    def test_the_movement_says_what_it_was_for(self, client):
        linked(client)
        fill(client, "VND", 50_000_000)
        position(client)

        row = movements_of(client)[0]
        assert (row["subject"], row["action"]) == ("asset", "buy")
        assert row["symbol"] == "VIC.VN"
        assert row["amount"] == pytest.approx(-9_000_000)
        assert row["currency"] == "VND"
        # No rate: the trade and the pot were the same money.
        assert row["rate"] is None

    def test_the_user_can_say_what_actually_left_the_account(self, client):
        """The one number the app cannot derive — a fee, or a rate the bank
        applied. The balance is the user's to state."""
        linked(client)
        fill(client, "VND", 50_000_000)
        response = client.post(
            "/api/assets",
            json={
                "symbol": "VIC.VN",
                "kind": "stock",
                "name": "Vingroup",
                "quantity": 100,
                "cost_basis": 9_000_000,
                "currency": "VND",
                "cash_amount": 9_050_000,
            },
        )
        created = response.json()
        assert created["cash"]["amount"] == pytest.approx(-9_050_000)
        assert balance_of(client) == pytest.approx(40_950_000)

    def test_a_position_with_no_cost_moves_nothing(self, client):
        linked(client)
        fill(client, "VND", 50_000_000)
        created = position(client, cost=None)
        assert created["cash"]["moved"] is False
        assert created["cash"]["skipped"] == "no_amount"
        assert balance_of(client) == 50_000_000

    def test_a_gold_purchase_leaves_the_dong_pot(self, client):
        from tests.test_gold import SJC_KEY

        linked(client)
        fill(client, "VND", 50_000_000)
        response = client.post(
            "/api/gold",
            json={
                "name": "SJC 5 chỉ",
                "currency": "VND",
                "quantity": 5,
                "unit": "chi",
                "product_key": SJC_KEY,
                "cost_basis": 70_000_000,
            },
        )
        assert response.status_code == 201, response.text
        holding = response.json()
        assert holding["cash"]["amount"] == pytest.approx(-70_000_000)
        assert balance_of(client) == pytest.approx(-20_000_000)
        assert movements_of(client)[0]["subject"] == "gold"

    def test_opening_a_deposit_moves_the_principal(self, client):
        linked(client)
        fill(client, "VND", 50_000_000)
        response = client.post(
            "/api/deposits",
            json={
                "name": "VCB 6 tháng",
                "currency": "VND",
                "principal": 30_000_000,
                "annual_rate": 5.5,
                "start_date": "2026-01-01",
                "maturity_date": "2026-07-01",
            },
        )
        deposit = response.json()
        assert deposit["cash"]["amount"] == pytest.approx(-30_000_000)
        assert balance_of(client) == pytest.approx(20_000_000)
        # Found by action, not by position: a deposit dated in the past sorts
        # below the line written today, which is what "newest first" means.
        row = next(row for row in movements_of(client) if row["action"] == "open")
        assert row["subject"] == "deposit"
        assert row["occurred_on"] == "2026-01-01"


# --------------------------------------------------------------------------
# Selling
# --------------------------------------------------------------------------


class TestSelling:
    def test_the_proceeds_land_in_the_pot(self, client):
        linked(client)
        fill(client, "VND", 50_000_000)
        position(client)

        sold = client.post(
            "/api/assets/1/sell",
            json={"quantity": 100, "proceeds": 12_000_000},
        ).json()
        assert sold["cash"]["moved"] is True
        assert sold["cash"]["amount"] == pytest.approx(12_000_000)
        # 50 000 000 − 9 000 000 to buy, + 12 000 000 to sell.
        assert balance_of(client) == pytest.approx(53_000_000)

    def test_selling_at_the_price_paid_leaves_the_pot_where_it_was(self, client):
        """The round trip has to be exactly neutral when nothing was gained:
        money left, money came back, and the balance is the same number."""
        linked(client)
        fill(client, "VND", 50_000_000)
        position(client, cost=9_000_000)
        client.post("/api/assets/1/sell", json={"quantity": 100, "proceeds": 9_000_000})

        assert balance_of(client) == pytest.approx(50_000_000)
        # And the trade's own two movements cancel, which is what makes the
        # round trip neutral.
        assert sum(row["amount"] for row in trades(client)) == pytest.approx(0)

    def test_a_dollar_sale_credits_the_dollar_pot(self, client):
        linked(client)
        fill(client, "VND", 0)
        fill(client, "USD", 0)
        position(client, symbol="AAPL", quantity=10, cost=1_500, currency="USD")
        client.post("/api/assets/1/sell", json={"quantity": 10, "proceeds": 2_000})

        # −1 500 USD + 2 000 USD, in dollars, with no rate involved.
        assert balance_of(client, "USD") == pytest.approx(500)
        assert balance_of(client, "VND") == 0
        assert movements_of(client)[0]["rate"] is None

    def test_proceeds_in_an_unconvertible_currency_are_reported_not_guessed(self, client):
        """`VWCE.DE` is quoted in EUR, which this app neither holds cash in nor
        converts. The sale is recorded; the cash side says why it did nothing."""
        linked(client)
        fill(client, "USD", 0)
        position(client, symbol="VWCE.DE", quantity=10, cost=900, currency="USD")
        after_buy = balance_of(client, "USD")
        assert after_buy == pytest.approx(-900)

        sold = client.post(
            "/api/assets/1/sell", json={"quantity": 10, "proceeds": 1_100}
        ).json()

        assert sold["symbol"] == "VWCE.DE"
        assert sold["proceeds_currency"] == "EUR"
        assert sold["cash"]["moved"] is False
        assert sold["cash"]["skipped"] == "no_rate"
        # Nothing was credited, and nothing was guessed at either.
        assert balance_of(client, "USD") == pytest.approx(after_buy)

    def test_the_user_can_say_what_actually_arrived(self, client):
        linked(client)
        fill(client, "USD", 0)
        position(client, symbol="AAPL", quantity=10, cost=1_500, currency="USD")
        after_buy = balance_of(client, "USD")

        sold = client.post(
            "/api/assets/1/sell",
            json={"quantity": 10, "proceeds": 2_000, "cash_amount": 1_980},
        ).json()
        assert sold["cash"]["amount"] == pytest.approx(1_980)
        assert balance_of(client, "USD") == pytest.approx(after_buy + 1_980)


# --------------------------------------------------------------------------
# Deleting and editing
# --------------------------------------------------------------------------


class TestDeleting:
    def test_deleting_a_purchase_gives_the_money_back(self, client):
        linked(client)
        fill(client, "VND", 50_000_000)
        created = position(client)
        removed = client.delete(f"/api/assets/{created['id']}").json()

        assert removed["cash"]["moved"] is True
        assert removed["cash"]["amount"] == pytest.approx(9_000_000)
        assert balance_of(client) == pytest.approx(50_000_000)

    def test_a_partly_sold_position_gives_back_what_is_left_in_it(self, client):
        """Bought for 9 000 000, half sold for 5 000 000 (a gain). The pot is
        4 000 000 down; that — not the 4 500 000 of remaining cost — is what
        comes back when the rest is deleted. The 1 000 000 of gain is already
        realised and stays realised."""
        linked(client)
        fill(client, "VND", 50_000_000)
        created = position(client, quantity=100, cost=9_000_000)
        client.post(
            f"/api/assets/{created['id']}/sell",
            json={"quantity": 50, "proceeds": 5_000_000},
        )
        assert balance_of(client) == pytest.approx(46_000_000)

        removed = client.delete(f"/api/assets/{created['id']}").json()
        assert removed["cash"]["amount"] == pytest.approx(4_000_000)
        assert balance_of(client) == pytest.approx(50_000_000)

    def test_deleting_something_that_never_came_out_of_cash_gives_nothing(self, client):
        """Recorded while the link was off: no money left the pot, so none may
        be put back. This is the rule that stops a delete from printing money."""
        fill(client, "VND", 50_000_000)
        created = position(client)
        linked(client, True)

        removed = client.delete(f"/api/assets/{created['id']}").json()
        assert removed["cash"]["moved"] is False
        assert removed["cash"]["skipped"] == "nothing_paid"
        assert balance_of(client) == 50_000_000

    def test_a_sale_that_returned_more_than_was_paid_gives_nothing_back(self, client):
        """Half of a position sold for more than the whole of it cost: the pot is
        already ahead of what it put in, and a delete must not add to that."""
        linked(client)
        fill(client, "VND", 50_000_000)
        created = position(client, quantity=100, cost=9_000_000)
        client.post(
            f"/api/assets/{created['id']}/sell",
            json={"quantity": 50, "proceeds": 20_000_000},
        )
        # −9 000 000 + 20 000 000: the pot is 11 000 000 ahead.
        assert balance_of(client) == pytest.approx(61_000_000)

        removed = client.delete(f"/api/assets/{created['id']}").json()
        assert removed["cash"]["moved"] is False
        assert removed["cash"]["skipped"] == "nothing_paid"
        assert balance_of(client) == pytest.approx(61_000_000)

    def test_deleting_a_deposit_gives_the_principal_back(self, client):
        linked(client)
        fill(client, "VND", 50_000_000)
        created = client.post(
            "/api/deposits",
            json={
                "name": "VCB",
                "currency": "VND",
                "principal": 30_000_000,
                "annual_rate": 5.5,
                "start_date": "2026-01-01",
                "maturity_date": "2026-07-01",
            },
        ).json()
        assert balance_of(client) == pytest.approx(20_000_000)

        removed = client.delete(f"/api/deposits/{created['id']}").json()
        assert removed["cash"]["amount"] == pytest.approx(30_000_000)
        assert balance_of(client) == pytest.approx(50_000_000)


class TestEditing:
    def test_raising_a_cost_basis_takes_the_difference(self, client):
        linked(client)
        fill(client, "VND", 50_000_000)
        created = position(client, cost=9_000_000)

        updated = client.patch(
            f"/api/assets/{created['id']}", json={"cost_basis": 10_000_000}
        ).json()
        assert updated["cash"]["moved"] is True
        assert updated["cash"]["amount"] == pytest.approx(-1_000_000)
        assert balance_of(client) == pytest.approx(40_000_000)

    def test_lowering_a_cost_basis_gives_the_difference_back(self, client):
        linked(client)
        fill(client, "VND", 50_000_000)
        created = position(client, cost=9_000_000)

        updated = client.patch(
            f"/api/assets/{created['id']}", json={"cost_basis": 8_000_000}
        ).json()
        assert updated["cash"]["amount"] == pytest.approx(1_000_000)
        assert balance_of(client) == pytest.approx(42_000_000)

    def test_clearing_a_cost_basis_moves_nothing(self, client):
        """The user has said they no longer know what it cost, not that they got
        the money back. Crediting the pot here would invent a movement."""
        linked(client)
        fill(client, "VND", 50_000_000)
        created = position(client, cost=9_000_000)

        updated = client.patch(
            f"/api/assets/{created['id']}", json={"cost_basis": None}
        ).json()
        assert updated["cost_basis"] is None
        assert updated["cash"] is None
        assert balance_of(client) == pytest.approx(41_000_000)
        # One trade movement only: the purchase.
        assert len(trades(client)) == 1

    def test_correcting_a_quantity_alone_moves_nothing(self, client):
        """A typo in how many units are held is not a purchase."""
        linked(client)
        fill(client, "VND", 50_000_000)
        created = position(client, quantity=100, cost=9_000_000)

        updated = client.patch(f"/api/assets/{created['id']}", json={"quantity": 90}).json()
        assert updated["cash"] is None
        assert balance_of(client) == pytest.approx(41_000_000)

    def test_editing_a_deposit_principal_moves_the_difference(self, client):
        linked(client)
        fill(client, "VND", 50_000_000)
        created = client.post(
            "/api/deposits",
            json={
                "name": "VCB",
                "currency": "VND",
                "principal": 30_000_000,
                "annual_rate": 5.5,
                "start_date": "2026-01-01",
                "maturity_date": "2026-07-01",
            },
        ).json()
        updated = client.patch(
            f"/api/deposits/{created['id']}", json={"principal": 35_000_000}
        ).json()
        assert updated["cash"]["amount"] == pytest.approx(-5_000_000)
        assert balance_of(client) == pytest.approx(15_000_000)

    def test_changing_a_rate_moves_nothing(self, client):
        """The rate is a term of the contract, not money."""
        linked(client)
        fill(client, "VND", 50_000_000)
        created = client.post(
            "/api/deposits",
            json={
                "name": "VCB",
                "currency": "VND",
                "principal": 30_000_000,
                "annual_rate": 5.5,
                "start_date": "2026-01-01",
                "maturity_date": "2026-07-01",
            },
        ).json()
        updated = client.patch(
            f"/api/deposits/{created['id']}", json={"annual_rate": 6.5}
        ).json()
        assert updated["cash"] is None
        assert balance_of(client) == pytest.approx(20_000_000)


# --------------------------------------------------------------------------
# Maturity
# --------------------------------------------------------------------------


class TestWithdrawing:
    def opened(self, client, **overrides):
        body = {
            "name": "VCB",
            "currency": "VND",
            "principal": 30_000_000,
            "annual_rate": 5.5,
            "start_date": "2020-01-01",
            "maturity_date": "2020-07-01",
        }
        body.update(overrides)
        response = client.post("/api/deposits", json=body)
        assert response.status_code == 201, response.text
        return response.json()

    def test_the_money_lands_in_the_pot_that_already_exists(self, client):
        """A term deposit is the same money coming back, not a new pile of it."""
        linked(client)
        fill(client, "VND", 0)
        created = self.opened(client)
        assert balance_of(client) == pytest.approx(-30_000_000)

        result = client.post(f"/api/deposits/{created['id']}/withdraw", json={}).json()
        assert result["cash"]["moved"] is True
        assert result["account"]["currency"] == "VND"
        assert result["account"]["balance"] == pytest.approx(
            result["amount"] - 30_000_000
        )
        # Still two pots: nothing was created for the money to land in.
        assert len(client.get("/api/cash").json()) == 2
        assert movements_of(client)[0]["action"] == "close"

    def test_it_lands_there_even_with_the_link_off(self, client):
        """The one movement the switch does not govern. With the link off there
        is still no other place for the money to go, and a balance that grew
        with no line of history is what the history exists to prevent."""
        fill(client, "VND", 50_000_000)
        created = self.opened(client)
        assert balance_of(client) == 50_000_000  # nothing moved on the way in

        result = client.post(f"/api/deposits/{created['id']}/withdraw", json={}).json()
        assert result["cash"]["moved"] is True
        assert balance_of(client) == pytest.approx(50_000_000 + result["amount"])
        assert movements_of(client)[0]["action"] == "close"

    def test_the_user_can_say_what_the_bank_actually_paid(self, client):
        linked(client)
        fill(client, "VND", 0)
        created = self.opened(client)
        result = client.post(
            f"/api/deposits/{created['id']}/withdraw", json={"balance": 31_000_000}
        ).json()
        assert result["amount"] == 31_000_000
        assert balance_of(client) == pytest.approx(1_000_000)


# --------------------------------------------------------------------------
# Money in and out, with no trade behind it
# --------------------------------------------------------------------------


class TestMoneyInAndOut:
    """The button the Cash page was missing: put money in, take money out."""

    def test_money_in_lands_and_leaves_a_line(self, client):
        result = client.post(
            "/api/cash/1/entry",
            json={"amount": 5_000_000, "direction": "in", "note": "Lương tháng 10"},
        )
        assert result.status_code == 200, result.text
        body = result.json()
        assert body["account"]["balance"] == pytest.approx(5_000_000)
        assert body["cash"]["moved"] is True
        assert body["cash"]["amount"] == pytest.approx(5_000_000)

        row = movements_of(client)[0]
        assert (row["subject"], row["action"]) == ("cash", "in")
        assert row["amount"] == pytest.approx(5_000_000)
        assert row["note"] == "Lương tháng 10"
        # No holding behind it, and nothing to convert.
        assert row["holding_id"] is None
        assert row["rate"] is None

    def test_money_out_leaves_a_negative_line(self, client):
        client.patch("/api/cash/1", json={"balance": 10_000_000})
        result = client.post(
            "/api/cash/1/entry",
            json={"amount": 2_000_000, "direction": "out", "note": "Tiền nhà"},
        ).json()
        assert result["account"]["balance"] == pytest.approx(8_000_000)
        assert result["cash"]["amount"] == pytest.approx(-2_000_000)
        assert movements_of(client)[0]["action"] == "out"

    def test_the_direction_is_a_word_not_a_sign(self, client):
        """A form asking for "-500000" to mean a withdrawal is a form that will
        one day record one the wrong way round, so the amount is positive and
        the direction is spelled out."""
        assert (
            client.post(
                "/api/cash/1/entry",
                json={"amount": -1, "direction": "in"},
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/cash/1/entry",
                json={"amount": 1, "direction": "sideways"},
            ).status_code
            == 422
        )

    def test_it_works_with_the_cash_link_off(self, client):
        """The link governs trades. Money the user puts in themselves is their
        own record of their own money, and a switch must not stop it."""
        assert client.get("/api/settings").json()["cash_linked"] is False
        client.post("/api/cash/1/entry", json={"amount": 1_000, "direction": "in"})
        assert pot(client, "VND")["balance"] == pytest.approx(1_000)

    def test_money_can_go_into_the_dollar_balance(self, client):
        usd = pot(client, "USD")["id"]
        client.post(
            f"/api/cash/{usd}/entry",
            json={"amount": 300, "direction": "in", "note": "Wise"},
        )
        assert balance_of(client, "USD") == 300
        assert balance_of(client, "VND") == 0
        assert movements_of(client)[0]["currency"] == "USD"

    def test_the_day_can_be_said(self, client):
        client.post(
            "/api/cash/1/entry",
            json={"amount": 100, "direction": "in", "occurred_on": "2026-03-01"},
        )
        assert movements_of(client)[0]["occurred_on"] == "2026-03-01"

    def test_an_entry_on_a_pot_that_does_not_exist_is_a_404(self, client):
        assert (
            client.post(
                "/api/cash/999/entry", json={"amount": 1, "direction": "in"}
            ).status_code
            == 404
        )


class TestTheBooksBalance:
    """The page prints one figure and says it is the sum of the lines under it."""

    def history_total(self, client, currency="VND") -> float:
        return sum(
            row["amount"] for row in movements_of(client) if row["currency"] == currency
        )

    def test_a_balance_typed_in_is_written_down_as_an_adjustment(self, client):
        result = client.patch("/api/cash/1", json={"balance": 20_000_000}).json()
        assert result["balance"] == pytest.approx(20_000_000)
        assert result["cash"]["moved"] is True
        assert result["cash"]["amount"] == pytest.approx(20_000_000)

        row = movements_of(client)[0]
        assert (row["subject"], row["action"]) == ("cash", "adjust")
        assert self.history_total(client) == pytest.approx(20_000_000)

    def test_recounting_writes_only_the_difference(self, client):
        client.patch("/api/cash/1", json={"balance": 20_000_000})
        client.patch("/api/cash/1", json={"balance": 19_500_000})

        assert [row["amount"] for row in movements_of(client)] == [
            pytest.approx(-500_000),
            pytest.approx(20_000_000),
        ]
        assert self.history_total(client) == pytest.approx(19_500_000)

    def test_renaming_moves_no_money_and_writes_no_line(self, client):
        client.patch("/api/cash/1", json={"balance": 1_000})
        before = len(movements_of(client))
        result = client.patch("/api/cash/1", json={"name": "Vietcombank"}).json()
        assert result["name"] == "Vietcombank"
        assert result["cash"] is None
        assert len(movements_of(client)) == before

    def test_a_balance_that_is_not_changed_writes_nothing(self, client):
        client.patch("/api/cash/1", json={"balance": 1_000})
        result = client.patch("/api/cash/1", json={"balance": 1_000}).json()
        assert result["cash"] is None
        assert len(movements_of(client)) == 1

    def test_the_balance_is_the_sum_of_its_history(self, client):
        """Trades, entries and a recount, all in one pot: the figure on the page
        and the lines under it agree at every step."""
        linked(client)
        client.post("/api/cash/1/entry", json={"amount": 50_000_000, "direction": "in"})
        position(client, cost=9_000_000)
        client.post("/api/assets/1/sell", json={"quantity": 100, "proceeds": 12_000_000})
        client.patch("/api/cash/1", json={"balance": 60_000_000})

        assert balance_of(client) == pytest.approx(60_000_000)
        assert self.history_total(client) == pytest.approx(60_000_000)


# --------------------------------------------------------------------------
# The history itself
# --------------------------------------------------------------------------


class TestTheHistory:
    def test_the_portfolio_carries_every_movement_newest_first(self, client):
        linked(client)
        fill(client, "VND", 50_000_000)
        position(client, symbol="VIC.VN", cost=1_000_000)
        position(client, symbol="FPT.VN", cost=2_000_000)

        rows = trades(client)
        assert [row["symbol"] for row in rows] == ["FPT.VN", "VIC.VN"]
        assert all(row["occurred_on"] == models.today_iso() for row in rows)

    def test_a_movement_outlives_the_holding_it_belongs_to(self, client):
        linked(client)
        fill(client, "VND", 50_000_000)
        created = position(client)
        client.delete(f"/api/assets/{created['id']}")

        rows = trades(client)
        # The purchase and the refund, and the name is still there to read.
        assert [row["action"] for row in rows] == ["refund", "buy"]
        assert all(row["symbol"] == "VIC.VN" for row in rows)
        assert all(row["holding_id"] == created["id"] for row in rows)

    def test_each_pot_keeps_its_own_side_of_the_history(self, client):
        """One list, two currencies in it: a dollar movement and a dong one are
        both on the record, each in the money it actually was."""
        linked(client)
        fill(client, "VND", 50_000_000)
        fill(client, "USD", 5_000)
        position(client, symbol="VIC.VN", cost=1_000_000)
        position(client, symbol="AAPL", quantity=1, cost=100, currency="USD")

        rows = trades(client)
        assert [row["currency"] for row in rows] == ["USD", "VND"]
        assert [row["amount"] for row in rows] == [-100, -1_000_000]

    def test_a_wipe_removes_the_movements_and_empties_the_pots(self, client):
        linked(client)
        fill(client, "VND", 50_000_000)
        position(client)

        removed = client.post("/api/settings/wipe").json()["removed"]
        # Two: the balance typed in, and the purchase.
        assert removed["movements"] == 2
        assert movements_of(client) == []
        # The pots survive the wipe, empty: cash still exists.
        assert [row["balance"] for row in client.get("/api/cash").json()] == [0.0, 0.0]

    def test_wiping_does_not_forget_whether_the_link_is_on(self, client):
        """The link is a setting, and a wipe keeps settings: the user asked for
        a clean portfolio, not for the app to change how it behaves."""
        linked(client, True)
        client.post("/api/settings/wipe")
        assert client.get("/api/settings").json()["cash_linked"] is True


# --------------------------------------------------------------------------
# The arithmetic, without HTTP
# --------------------------------------------------------------------------


class TestNetInvested:
    def test_it_adds_the_movements_of_one_holding_only(self, db):
        cash.ensure_pots(db)
        db.commit()
        keeper = cash.pot(db, "VND")

        for amount, holding in ((-100.0, 1), (-50.0, 2), (30.0, 1)):
            db.add(
                models.CashMovement(
                    account_id=keeper.id,
                    subject="asset",
                    action="buy",
                    holding_id=holding,
                    name="x",
                    amount=amount,
                    currency="VND",
                    occurred_on="2026-01-01",
                )
            )
        db.commit()

        assert movements.net_invested(
            db, subject="asset", holding_id=1
        ) == pytest.approx(-70.0)
        assert movements.net_invested(
            db, subject="asset", holding_id=2
        ) == pytest.approx(-50.0)
        assert movements.net_invested(db, subject="asset", holding_id=99) == 0.0

    def test_a_holding_of_another_kind_is_not_counted(self, db):
        cash.ensure_pots(db)
        db.commit()
        db.add(
            models.CashMovement(
                account_id=cash.pot(db, "VND").id,
                subject="gold",
                action="buy",
                holding_id=1,
                name="x",
                amount=-100.0,
                currency="VND",
                occurred_on="2026-01-01",
            )
        )
        db.commit()
        assert movements.net_invested(db, subject="asset", holding_id=1) == 0.0


class TestTheSetting:
    def test_the_stored_value_is_a_yes_or_a_no(self, db):
        from app import settings_store

        assert settings_store.cash_linked(db) is False
        settings_store.set_cash_linked(db, True)
        assert settings_store.cash_linked(db) is True
        settings_store.set_cash_linked(db, "false")
        assert settings_store.cash_linked(db) is False

    def test_anything_else_is_refused(self, db):
        from app import settings_store

        with pytest.raises(settings_store.SettingRefused):
            settings_store.set_cash_linked(db, "maybe")

    def test_an_unreadable_value_fails_to_the_quiet_behaviour(self, db):
        """A setting that decides whether money moves must never fail towards
        editing balances."""
        from app import settings_store

        db.add(models.Setting(key=settings_store.CASH_LINKED_KEY, value="???"))
        db.commit()
        assert settings_store.cash_linked(db) is False


# --------------------------------------------------------------------------
# The pots themselves
# --------------------------------------------------------------------------


class TestThePots:
    def test_making_them_twice_creates_nothing_the_second_time(self, db):
        assert cash.ensure_pots(db) == ["VND", "USD"]
        assert cash.ensure_pots(db) == []
        assert len(cash.pots(db)) == 2

    def test_a_write_with_no_pots_at_all_makes_them(self, db):
        """A database that has never been read and has no cash in it yet."""
        assert cash.pots(db) == []
        account = movements.pot_for(db, "USD")
        assert account is not None and account.currency == "USD"
        assert [row.currency for row in cash.pots(db)] == ["VND", "USD"]

    def test_a_currency_with_no_pot_falls_back_to_dong(self, db):
        cash.ensure_pots(db)
        assert movements.pot_for(db, "EUR").currency == "VND"

    def test_a_copy_of_the_file_is_made_before_merging(self, tmp_path):
        """The rule this repository set for itself: a migration needs a copy of
        the file first. `sqlite3`'s own backup API, so the WAL comes with it."""
        import sqlite3

        source = tmp_path / "data.db"
        with sqlite3.connect(source) as connection:
            connection.execute("CREATE TABLE t (x INTEGER)")
            connection.execute("INSERT INTO t VALUES (1)")
            # In WAL mode the newest commits live outside the main file, which
            # is exactly what a `shutil.copy` would miss.
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("INSERT INTO t VALUES (2)")

        backup = cash.copy_database(source)
        assert backup is not None and backup.is_file()
        assert "before-merge" in backup.name
        with sqlite3.connect(backup) as copy:
            assert copy.execute("SELECT count(*) FROM t").fetchone()[0] == 2

    def test_merging_leaves_a_single_pot_alone(self, db):
        cash.ensure_pots(db)
        assert cash.merge_duplicates(db) == []
        assert len(cash.pots(db)) == 2

    def test_a_balance_with_no_history_gets_a_line_of_its_own(self, db):
        """The normal state of a portfolio that existed before the history did:
        money in the pot, and nothing explaining it. It is written down once
        rather than left as a silent opening figure."""
        cash.ensure_pots(db)
        vnd = cash.pot(db, "VND")
        vnd.balance = 20_000_000
        vnd.balance_at = "2026-05-01"
        db.commit()

        written = cash.reconcile(db)
        assert written == ["VND: +2e+07"]
        row = db.query(models.CashMovement).one()
        assert (row.subject, row.action) == ("cash", "adjust")
        assert row.amount == pytest.approx(20_000_000)
        # Dated the day the balance was counted, not the day it was noticed.
        assert row.occurred_on == "2026-05-01"

    def test_reconciling_twice_writes_nothing_the_second_time(self, db):
        cash.ensure_pots(db)
        cash.pot(db, "VND").balance = 5_000
        db.commit()

        assert cash.reconcile(db) == ["VND: +5000"]
        assert cash.reconcile(db) == []

    def test_an_empty_pot_needs_no_explaining(self, db):
        cash.ensure_pots(db)
        assert cash.reconcile(db) == []
        assert db.query(models.CashMovement).count() == 0
