"""The HTTP surface: what it accepts, what it refuses, what it returns.

These tests go through the real app (routers, schemas, serialisation) against
the fake market and the fake feed, so they check the contract the frontend is
written against, not just the functions behind it.
"""

from __future__ import annotations

import datetime

import pytest


class TestHealth:
    def test_the_app_answers(self, client):
        body = client.get("/api/health").json()
        assert body["status"] == "ok"
        assert body["version"]


class TestSettings:
    def test_a_fresh_install_is_dong_and_vietnamese(self, client):
        body = client.get("/api/settings").json()
        assert body["base_currency"] == "VND"
        assert body["language"] == "vi"

    def test_the_supported_lists_come_from_the_server(self, client):
        body = client.get("/api/settings").json()
        assert body["supported_currencies"] == ["VND", "USD"]
        assert body["supported_languages"] == ["vi", "en"]
        assert body["supported_kinds"] == ["stock", "fund", "crypto", "cash"]

    def test_the_language_can_be_changed(self, client):
        assert client.patch("/api/settings", json={"language": "en"}).json()["language"] == "en"

    def test_a_language_that_does_not_exist_is_refused(self, client):
        assert client.patch("/api/settings", json={"language": "fr"}).status_code == 422

    def test_a_third_currency_is_refused_as_a_base(self, client):
        assert client.patch("/api/settings", json={"base_currency": "EUR"}).status_code == 422

    def test_changing_the_base_re_expresses_every_total(self, client):
        client.post("/api/cash", json={"name": "Vietcombank", "currency": "VND", "balance": 26_000_000})
        assert client.get("/api/portfolio").json()["total"] == pytest.approx(26_000_000)
        client.patch("/api/settings", json={"base_currency": "USD"})
        assert client.get("/api/portfolio").json()["total"] == pytest.approx(1_000)


class TestAssets:
    def test_a_position_can_be_added_and_is_valued_on_the_way_out(self, client):
        response = client.post(
            "/api/assets",
            json={
                "symbol": "aapl",
                "kind": "stock",
                "name": "Apple Inc.",
                "quantity": 10,
                "cost_basis": 1_500,
                "currency": "USD",
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["symbol"] == "AAPL"  # normalised on the way in
        assert body["price"] == 200.0
        assert body["value_base"] == pytest.approx(52_000_000)
        assert body["gain"] == pytest.approx(13_000_000)

    def test_an_asset_kind_of_cash_is_refused(self, client):
        # Cash has its own endpoints; letting it in here would create a
        # position with no price and a quantity that means nothing.
        response = client.post(
            "/api/assets",
            json={"symbol": "X", "kind": "cash", "quantity": 1, "currency": "USD"},
        )
        assert response.status_code == 422

    def test_a_currency_outside_the_two_is_refused(self, client):
        response = client.post(
            "/api/assets",
            json={"symbol": "VWCE.DE", "kind": "fund", "quantity": 1, "currency": "EUR"},
        )
        assert response.status_code == 422

    def test_a_negative_quantity_is_refused(self, client):
        response = client.post(
            "/api/assets",
            json={"symbol": "AAPL", "kind": "stock", "quantity": -1, "currency": "USD"},
        )
        assert response.status_code == 422

    def test_a_position_can_be_edited(self, client):
        created = client.post(
            "/api/assets",
            json={"symbol": "AAPL", "kind": "stock", "quantity": 10, "currency": "USD"},
        ).json()
        updated = client.patch(f"/api/assets/{created['id']}", json={"quantity": 20}).json()
        assert updated["value_base"] == pytest.approx(104_000_000)

    def test_a_position_can_be_deleted(self, client):
        created = client.post(
            "/api/assets",
            json={"symbol": "AAPL", "kind": "stock", "quantity": 1, "currency": "USD"},
        ).json()
        assert client.delete(f"/api/assets/{created['id']}").status_code == 204
        assert client.get("/api/assets").json() == []

    def test_reading_a_position_that_is_not_there_is_a_404(self, client):
        assert client.get("/api/assets/999").status_code == 404

    def test_selling_everything_leaves_a_position_worth_nothing_but_visible(self, client):
        created = client.post(
            "/api/assets",
            json={"symbol": "AAPL", "kind": "stock", "quantity": 10, "currency": "USD"},
        ).json()
        body = client.patch(f"/api/assets/{created['id']}", json={"quantity": 0}).json()
        assert body["quantity"] == 0
        assert body["value_base"] is None
        assert body["reason"] == "no_quantity"

    def test_the_list_can_be_filtered_by_kind(self, client):
        client.post("/api/assets", json={"symbol": "AAPL", "kind": "stock", "quantity": 1, "currency": "USD"})
        client.post("/api/assets", json={"symbol": "BTC-USD", "kind": "crypto", "quantity": 1, "currency": "USD"})
        only_crypto = client.get("/api/assets", params={"kind": "crypto"}).json()
        assert [row["symbol"] for row in only_crypto] == ["BTC-USD"]


class TestCash:
    def test_a_balance_can_be_written_down(self, client):
        body = client.post(
            "/api/cash", json={"name": "Vietcombank", "currency": "VND", "balance": 50_000_000}
        ).json()
        assert body["balance"] == 50_000_000
        assert body["value_base"] == pytest.approx(50_000_000)
        assert body["balance_at"]

    def test_the_manual_update_is_one_patch(self, client):
        created = client.post(
            "/api/cash", json={"name": "Vietcombank", "currency": "VND", "balance": 1}
        ).json()
        updated = client.patch(f"/api/cash/{created['id']}", json={"balance": 75_000_000}).json()
        assert updated["balance"] == 75_000_000
        assert updated["value_base"] == pytest.approx(75_000_000)

    def test_renaming_does_not_restamp_the_balance(self, client, db):
        created = client.post(
            "/api/cash", json={"name": "Old", "currency": "VND", "balance": 1}
        ).json()
        # Pretend the balance was written down a week ago.
        from app import models

        row = db.get(models.CashAccount, created["id"])
        row.balance_at = "2026-01-01"
        db.commit()

        renamed = client.patch(f"/api/cash/{created['id']}", json={"name": "New"}).json()
        assert renamed["name"] == "New"
        assert renamed["balance_at"] == "2026-01-01"

    def test_changing_the_balance_does_restamp_it(self, client, db):
        from app import models

        created = client.post(
            "/api/cash", json={"name": "Old", "currency": "VND", "balance": 1}
        ).json()
        row = db.get(models.CashAccount, created["id"])
        row.balance_at = "2026-01-01"
        db.commit()

        updated = client.patch(f"/api/cash/{created['id']}", json={"balance": 2}).json()
        assert updated["balance_at"] != "2026-01-01"

    def test_cash_in_dollars_is_converted(self, client):
        body = client.post(
            "/api/cash", json={"name": "Wise", "currency": "USD", "balance": 100}
        ).json()
        assert body["value_base"] == pytest.approx(2_600_000)

    def test_a_third_currency_is_refused(self, client):
        response = client.post(
            "/api/cash", json={"name": "Revolut", "currency": "EUR", "balance": 100}
        )
        assert response.status_code == 422

    def test_a_balance_can_be_deleted(self, client):
        created = client.post("/api/cash", json={"name": "X", "currency": "VND", "balance": 1}).json()
        assert client.delete(f"/api/cash/{created['id']}").status_code == 204
        assert client.get("/api/cash").json() == []


class TestPortfolio:
    def test_an_empty_portfolio_is_zero_and_not_an_error(self, client):
        body = client.get("/api/portfolio").json()
        assert body["total"] == 0.0
        assert body["assets"] == []
        assert body["cash"] == []
        assert body["counts"]["assets"] == 0

    def test_the_portfolio_carries_its_parts_and_its_rates(self, client):
        client.post("/api/cash", json={"name": "Wise", "currency": "USD", "balance": 100})
        body = client.get("/api/portfolio").json()
        assert body["base_currency"] == "VND"
        assert body["cash_value"] == pytest.approx(2_600_000)
        assert body["total"] == pytest.approx(2_600_000)
        assert body["rates"][0]["currency"] == "USD"
        assert body["rates"][0]["currency"] == "USD"

    def test_switching_the_base_never_leaves_a_position_unconverted(self, client):
        """A base with no rate in it would read a whole portfolio as nothing.

        The app seeds rates for every base it can be read in, so switching
        cannot silently empty the total.
        """
        client.post(
            "/api/assets",
            json={"symbol": "AAPL", "kind": "stock", "quantity": 10, "currency": "USD"},
        )
        client.post("/api/cash", json={"name": "Vietcombank", "currency": "VND", "balance": 26_000_000})

        client.patch("/api/settings", json={"base_currency": "USD"})
        switched = client.get("/api/portfolio").json()
        assert switched["total"] == pytest.approx(3_000)
        assert switched["unconverted"] == []

    def test_history_returns_points_in_the_order_they_were_recorded(self, client, db):
        """Points from different days come back oldest first.

        Written straight into the table: the endpoint is what is under test,
        and a test that had to wait for tomorrow to check ordering would never
        be run.
        """
        from app import models

        db.add(
            models.Valuation(
                as_of="2026-01-02", base_currency="VND", total=3.0, market_value=3.0
            )
        )
        db.add(
            models.Valuation(
                as_of="2026-01-01", base_currency="USD", total=1.0, market_value=1.0
            )
        )
        db.commit()

        points = client.get("/api/portfolio/history").json()["points"]
        assert [(point["as_of"], point["base_currency"]) for point in points] == [
            ("2026-01-01", "USD"),
            ("2026-01-02", "VND"),
        ]

    def test_a_history_point_can_be_deleted(self, client, db):
        from app import models

        db.add(
            models.Valuation(
                as_of="2026-01-01", base_currency="VND", total=1.0, market_value=1.0
            )
        )
        db.commit()
        assert client.delete("/api/portfolio/history/2026-01-01").status_code == 204
        assert client.get("/api/portfolio/history").json()["points"] == []

    def test_a_snapshot_can_be_written_and_read_back(self, client):
        client.post("/api/cash", json={"name": "Wise", "currency": "VND", "balance": 1_000})
        written = client.post("/api/portfolio/snapshot").json()
        assert written["total"] == pytest.approx(1_000)
        history = client.get("/api/portfolio/history").json()
        assert history["points"][0]["as_of"] == written["as_of"]


class TestMarketEndpoints:
    def test_a_query_returns_suggestions_with_their_currency(self, client):
        body = client.get("/api/market/search", params={"q": "aapl"}).json()
        assert body["degraded"] is False
        assert body["suggestions"][0]["symbol"] == "AAPL"
        assert body["suggestions"][0]["currency"] == "USD"

    def test_a_symbol_that_search_misses_is_resolved_directly(self, client):
        body = client.get("/api/market/search", params={"q": "VIC.VN"}).json()
        assert body["suggestions"][0]["symbol"] == "VIC.VN"

    def test_an_unreachable_search_degrades_instead_of_failing(self, client, monkeypatch):
        from app import market

        def explode(*_args, **_kwargs):
            raise market.MarketError("no")

        monkeypatch.setattr(market, "_fetch_search", explode)
        response = client.get("/api/market/search", params={"q": "aapl"})
        assert response.status_code == 200
        # It still resolved the ticker through the quote endpoint.
        assert response.json()["suggestions"]

    def test_refresh_reports_what_it_could_not_price(self, client):
        client.post("/api/assets", json={"symbol": "AAPL", "kind": "stock", "quantity": 1, "currency": "USD"})
        body = client.post("/api/prices/refresh").json()
        assert body["ok"] is True
        assert body["refreshed"] == ["AAPL"]

    def test_a_ticker_the_market_does_not_know_does_not_break_the_refresh(self, client):
        client.post("/api/assets", json={"symbol": "NOPE.XX", "kind": "stock", "quantity": 1, "currency": "USD"})
        body = client.post("/api/prices/refresh").json()
        assert body["ok"] is False
        assert body["failed"][0]["symbol"] == "NOPE.XX"
        assert body["failed"][0]["error"]

    def test_the_cached_market_can_be_read_with_its_dates(self, client):
        client.post("/api/assets", json={"symbol": "AAPL", "kind": "stock", "quantity": 1, "currency": "USD"})
        body = client.get("/api/market").json()
        assert body["prices"][0]["as_of"] == "2026-01-15"
        assert body["prices"][0]["fetched_at"]

    def test_rates_can_be_refreshed_and_read(self, client):
        assert client.post("/api/fx/refresh").json()["ok"] is True
        rates = client.get("/api/fx").json()
        assert any(row["source"] == "feed" for row in rates)

    def test_the_one_refresh_button_does_both(self, client):
        client.post("/api/assets", json={"symbol": "AAPL", "kind": "stock", "quantity": 1, "currency": "USD"})
        body = client.post("/api/refresh").json()
        assert body["prices"]["refreshed"] == ["AAPL"]
        assert body["fx"]["ok"] is True


class TestANameThatWouldBeNothing:
    """A blank name must be refused in words, never by a database constraint.

    The failure this guards is a 500: SQLite says "NOT NULL constraint failed",
    the browser shows nothing useful, and the user concludes the app lost their
    position when in fact it never wrote it.
    """

    def test_a_position_can_be_created_without_a_name(self, client):
        body = client.post(
            "/api/assets",
            json={"symbol": "AAPL", "kind": "stock", "quantity": 1, "currency": "USD"},
        ).json()
        assert body["name"] == "AAPL"

    def test_clearing_a_name_leaves_the_symbol_in_its_place(self, client):
        created = client.post(
            "/api/assets",
            json={"symbol": "aapl", "kind": "stock", "name": "Apple Inc.",
                  "quantity": 1, "currency": "USD"},
        ).json()
        updated = client.patch(f"/api/assets/{created['id']}", json={"name": "  "}).json()
        assert updated["name"] == "AAPL"

    def test_an_empty_name_is_refused_with_a_422(self, client):
        created = client.post(
            "/api/assets",
            json={"symbol": "AAPL", "kind": "stock", "quantity": 1, "currency": "USD"},
        ).json()
        response = client.patch(f"/api/assets/{created['id']}", json={"name": ""})
        assert response.status_code == 422

    def test_the_refusal_says_which_field_is_wrong(self, client):
        created = client.post(
            "/api/assets",
            json={"symbol": "AAPL", "kind": "stock", "quantity": 1, "currency": "USD"},
        ).json()
        detail = client.patch(f"/api/assets/{created['id']}", json={"name": ""}).json()["detail"]
        assert "name" in str(detail)


class TestWiping:
    """Deleting everything, without deleting the ability to start again."""

    def test_a_wipe_removes_the_positions_the_cash_and_the_history(self, client):
        client.post(
            "/api/assets",
            json={"symbol": "AAPL", "kind": "stock", "quantity": 1, "currency": "USD"},
        )
        client.post("/api/cash", json={"name": "Wise", "currency": "USD", "balance": 1})
        client.post("/api/portfolio/snapshot")

        removed = client.post("/api/settings/wipe").json()["removed"]
        assert removed["assets"] == 1
        assert removed["cash"] == 1
        assert removed["valuations"] == 1

        portfolio = client.get("/api/portfolio").json()
        assert portfolio["assets"] == []
        assert portfolio["cash"] == []
        assert portfolio["total"] == 0.0
        assert client.get("/api/portfolio/history").json()["points"] == []

    def test_a_wipe_keeps_what_makes_the_app_work(self, client):
        """The rate and the display currency survive: a fresh start must still
        be able to convert something, or the user is left with an app that
        cannot add up what they are about to type in."""
        client.post("/api/cash", json={"name": "Wise", "currency": "USD", "balance": 1})
        client.post("/api/settings/wipe")

        settings = client.get("/api/settings").json()
        assert settings["base_currency"] == "VND"
        assert client.get("/api/fx").json() != []

    def test_a_wipe_of_an_empty_database_is_not_an_error(self, client):
        assert client.post("/api/settings/wipe").json()["removed"] == {
            "assets": 0,
            "cash": 0,
            "valuations": 0,
        }


class TestDeposits:
    """The savings endpoints, including the two things that only happen at
    maturity: rolling over, and taking the money out."""

    def _create(self, client, **overrides):
        body = {
            "name": "Vietcombank 6 tháng",
            "currency": "VND",
            "principal": 500_000_000,
            "annual_rate": 6.0,
            "start_date": "2026-01-01",
            "maturity_date": "2026-07-01",
        }
        body.update(overrides)
        return client.post("/api/deposits", json=body)

    def test_a_deposit_can_be_opened(self, client):
        response = self._create(client)
        assert response.status_code == 201
        body = response.json()
        assert body["principal"] == 500_000_000
        assert body["annual_rate"] == 6.0
        assert body["value"] >= body["principal"]
        assert body["interest_accrued"] >= 0
        assert "T" not in body["as_of"]  # a date, not a timestamp

    def test_a_rate_above_one_hundred_percent_is_refused(self, client):
        assert self._create(client, annual_rate=150).status_code == 422

    def test_a_principal_of_zero_is_refused(self, client):
        assert self._create(client, principal=0).status_code == 422

    def test_a_maturity_before_the_start_is_refused(self, client):
        response = self._create(client, start_date="2026-07-01", maturity_date="2026-01-01")
        assert response.status_code == 422

    def test_a_demand_deposit_has_no_maturity_date(self, client):
        body = self._create(client, maturity_date=None).json()
        assert body["maturity_date"] is None
        assert body["matured"] is False
        assert body["days_remaining"] is None

    def test_a_deposit_counts_towards_the_portfolio_total(self, client):
        before = client.get("/api/portfolio").json()
        self._create(client)
        after = client.get("/api/portfolio").json()
        assert after["deposit_value"] > 0
        assert after["total"] == pytest.approx(before["total"] + after["deposit_value"])
        assert after["counts"]["deposits"] == 1

    def test_a_deposit_appears_as_its_own_kind(self, client):
        self._create(client)
        kinds = {row["kind"]: row for row in client.get("/api/portfolio").json()["by_kind"]}
        assert kinds["deposit"]["count"] == 1
        assert kinds["deposit"]["value"] > 0

    def test_a_dollar_deposit_is_converted(self, client):
        # A one-day term, so `value` is the principal and this test is about
        # the conversion rather than about the interest arithmetic.
        body = self._create(
            client,
            currency="USD",
            principal=10_000,
            annual_rate=4.0,
            start_date="2026-01-01",
            maturity_date="2026-01-02",
        ).json()
        assert body["value_base"] == pytest.approx(10_000 * 26_000, rel=0.001)

    def test_a_deposit_in_a_currency_the_app_cannot_hold_is_refused(self, client):
        assert self._create(client, currency="EUR").status_code == 422

    def test_a_deposit_can_be_edited(self, client):
        created = self._create(client).json()
        updated = client.patch(
            f"/api/deposits/{created['id']}", json={"annual_rate": 7.5}
        ).json()
        assert updated["annual_rate"] == 7.5
        assert updated["interest_accrued"] > created["interest_accrued"]

    def test_editing_to_a_maturity_before_the_start_is_refused(self, client):
        created = self._create(client).json()
        response = client.patch(
            f"/api/deposits/{created['id']}", json={"maturity_date": "2025-01-01"}
        )
        assert response.status_code == 422

    def test_a_deposit_can_be_deleted(self, client):
        created = self._create(client).json()
        assert client.delete(f"/api/deposits/{created['id']}").status_code == 204
        assert client.get("/api/deposits").json() == []

    def test_the_schedule_runs_to_maturity(self, client):
        created = self._create(client).json()
        points = client.get(f"/api/deposits/{created['id']}/schedule").json()
        assert points[-1]["as_of"] == "2026-07-01"
        assert points[-1]["value"] >= points[0]["value"]
        values = [point["value"] for point in points]
        assert values == sorted(values)

    def test_the_schedule_of_an_ended_term_is_the_one_point_that_matters(self, client):
        created = self._create(
            client, start_date="2020-01-01", maturity_date="2020-07-01"
        ).json()
        points = client.get(f"/api/deposits/{created['id']}/schedule").json()
        assert [point["as_of"] for point in points] == ["2020-07-01"]
        assert points[0]["matured"] is True

    def test_listing_can_be_filtered_to_what_has_matured(self, client):
        self._create(client, start_date="2020-01-01", maturity_date="2020-07-01")
        self._create(client, start_date="2099-01-01", maturity_date="2099-07-01")
        assert len(client.get("/api/deposits").json()) == 2
        assert len(client.get("/api/deposits", params={"matured": True}).json()) == 1
        assert len(client.get("/api/deposits", params={"matured": False}).json()) == 1

    def test_rolling_over_moves_the_interest_into_the_principal(self, client):
        # A term that ended yesterday: rolling it over is a decision about the
        # present, so the new term has to run into the future.
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        half_a_year_before = yesterday - datetime.timedelta(days=181)
        created = self._create(
            client,
            start_date=half_a_year_before.isoformat(),
            maturity_date=yesterday.isoformat(),
        ).json()
        rolled = client.post(f"/api/deposits/{created['id']}/roll", json={}).json()

        # The interest must not vanish: it becomes the new principal.
        assert rolled["principal"] == pytest.approx(created["value"])
        assert rolled["principal"] > 500_000_000
        # Same bank, same rate, a new period of the same length.
        assert rolled["name"] == created["name"]
        assert rolled["annual_rate"] == created["annual_rate"]
        assert rolled["start_date"] == yesterday.isoformat()
        assert rolled["maturity_date"] == (
            yesterday + datetime.timedelta(days=181)
        ).isoformat()
        assert rolled["matured"] is False
        # One day has already passed since the new term began (it began
        # yesterday), so 181 days of term means 180 days still to run.
        assert rolled["days_remaining"] == 180

    def test_rolling_over_can_change_the_rate_and_the_principal(self, client):
        created = self._create(
            client, start_date="2020-01-01", maturity_date="2020-07-01"
        ).json()
        rolled = client.post(
            f"/api/deposits/{created['id']}/roll",
            json={"annual_rate": 8.0, "principal": 600_000_000},
        ).json()
        assert rolled["annual_rate"] == 8.0
        assert rolled["principal"] == 600_000_000

    def test_a_deposit_that_has_not_matured_cannot_be_rolled_over(self, client):
        created = self._create(
            client, start_date="2099-01-01", maturity_date="2099-07-01"
        ).json()
        response = client.post(f"/api/deposits/{created['id']}/roll", json={})
        assert response.status_code == 422
        # And it is still there, unchanged.
        assert client.get(f"/api/deposits/{created['id']}").json()["principal"] == 500_000_000

    def test_withdrawing_closes_the_deposit_and_creates_cash(self, client):
        created = self._create(
            client, start_date="2020-01-01", maturity_date="2020-07-01"
        ).json()
        result = client.post(f"/api/deposits/{created['id']}/withdraw", json={}).json()

        assert result["amount"] == pytest.approx(created["value"])
        assert result["cash"]["balance"] == pytest.approx(created["value"])
        assert result["cash"]["currency"] == "VND"
        # The deposit is gone, so the money is not counted twice.
        assert client.get("/api/deposits").json() == []
        assert len(client.get("/api/cash").json()) == 1

    def test_withdrawing_can_name_the_account_and_the_amount(self, client):
        created = self._create(
            client, start_date="2020-01-01", maturity_date="2020-07-01"
        ).json()
        result = client.post(
            f"/api/deposits/{created['id']}/withdraw",
            json={"account_name": "Vietcombank tiết kiệm", "balance": 600_000_000},
        ).json()
        assert result["cash"]["name"] == "Vietcombank tiết kiệm"
        assert result["cash"]["balance"] == 600_000_000

    def test_a_withdrawal_leaves_the_total_whole(self, client):
        """Moving money between two tables must not create or destroy any."""
        created = self._create(
            client, start_date="2020-01-01", maturity_date="2020-07-01"
        ).json()
        before = client.get("/api/portfolio").json()["total"]
        client.post(f"/api/deposits/{created['id']}/withdraw", json={})
        after = client.get("/api/portfolio").json()["total"]
        assert after == pytest.approx(before)

    def test_a_deposit_can_be_withdrawn_before_maturity(self, client):
        """Taking money out early is the bank's business, not this app's.

        The app records what the user says the money became; it does not refuse
        to record a withdrawal the bank has already made.
        """
        created = self._create(
            client, start_date="2099-01-01", maturity_date="2099-07-01"
        ).json()
        response = client.post(
            f"/api/deposits/{created['id']}/withdraw", json={"balance": 500_000_000}
        )
        assert response.status_code == 200
        assert response.json()["amount"] == 500_000_000
