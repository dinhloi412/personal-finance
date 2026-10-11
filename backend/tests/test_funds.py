"""Open-ended funds: the alias table, the NAV, and the fallback that finds them.

The interesting failures here are not network failures — those are handled the
same way everywhere in this app — they are the two ways a fund goes missing:

1. **The code a person types is not the code the source uses.** `DCDE` is
   Dragon Capital's name for the fund Fmarket publishes as `VFMVF4`. Both are
   correct; a lookup that only knows one of them finds nothing, and nothing
   looks exactly like "Yahoo does not have this fund", which was the original
   complaint.
2. **A fund is not a listing.** Yahoo will never price it, so a refresh that
   only asks Yahoo reports a failure for a fund that is perfectly priceable.
   `tests` here pin the fallback, because the symptom of its absence is the
   same as the symptom of the fund genuinely not existing.
"""

from __future__ import annotations

import datetime

import pytest

from app import funds, models, pricing


class TestTheAliasTable:
    def test_the_code_a_person_types_resolves_to_the_source_code(self):
        assert funds.resolve_product_code("DCDE") == "VFMVF4"
        assert funds.resolve_product_code("DCDS") == "VFMVF1"

    def test_case_and_whitespace_are_forgiven(self):
        assert funds.resolve_product_code("  dcde ") == "VFMVF4"

    def test_a_code_that_needs_no_aliasing_is_left_alone(self):
        assert funds.resolve_product_code("VNDAF") == "VNDAF"

    def test_the_table_only_maps_names_that_actually_differ(self):
        # A mapping from a code to itself is a row that does nothing and hides
        # the fact that the code was checked.
        for alias, code in funds.ALIASES.items():
            assert alias != code, f"{alias} maps to itself"
            assert alias == alias.strip().upper(), f"{alias} is not normalised"

    def test_the_two_funds_the_user_holds_are_both_known(self):
        """The point of the table, stated once: both names resolve."""
        for typed in ("VNDAF", "DCDE"):
            assert funds.resolve_product_code(typed), typed


class TestAQuote:
    def test_a_fund_is_priced_by_its_nav(self):
        priced = funds.quote("VNDAF")
        assert priced.nav == pytest.approx(18_049.76)
        assert priced.currency == "VND"
        assert priced.symbol == "VNDAF"

    def test_the_alias_keeps_the_name_it_was_asked_for(self):
        priced = funds.quote("DCDE")
        # The user's own code travels with the quote…
        assert priced.symbol == "DCDE"
        # …and the source's code travels beside it, so the picker can show both.
        assert priced.product_code == "VFMVF4"
        assert priced.nav == pytest.approx(24_582.29)

    def test_the_nav_carries_the_day_the_fund_valued_it(self):
        # Not the day of the request: a NAV is published once a day and the
        # delay is normal, so the date has to be the fund's own.
        priced = funds.quote("VNDAF")
        assert priced.as_of == "2026-10-09"

    def test_a_fund_the_source_does_not_carry_raises(self):
        # A missing NAV must be loud: the alternative is a position valued at
        # nothing, which is a number the user would believe.
        with pytest.raises(funds.FundError):
            funds.quote("NOPE")

    def test_an_unreachable_source_raises_rather_than_returning_zero(self, monkeypatch):
        def explode(_code):
            raise OSError("no route to host")

        monkeypatch.setattr(funds, "_fetch_product", explode)
        with pytest.raises(funds.FundError):
            funds.quote("VNDAF")

    def test_a_product_with_no_nav_is_not_offered(self, monkeypatch):
        monkeypatch.setattr(
            funds, "_fetch_product", lambda _c: {"code": "VNDAF", "nav": None}
        )
        with pytest.raises(funds.FundError):
            funds.quote("VNDAF")


class TestTheCatalogueAndSearch:
    def test_searching_finds_a_fund_by_its_own_code(self):
        assert [f.symbol for f in funds.search("VNDAF")] == ["VNDAF"]

    def test_searching_by_the_source_code_finds_the_public_one(self):
        """Typing the name the platform uses must work too: a person may have
        seen `VFMVF4` on a statement and `DCDE` on a certificate."""
        found = funds.search("VFMVF4")
        assert [f.symbol for f in found] == ["DCDE"]

    def test_searching_by_the_manager_finds_their_funds(self):
        found = {f.symbol for f in funds.search("DCVFM")}
        assert "DCDE" in found

    def test_searching_by_name_works(self):
        assert [f.symbol for f in funds.search("cổ tức")] == ["DCDE"]

    def test_an_exact_code_comes_first(self):
        """A code typed exactly wins over a fund that merely mentions it.

        Asked for `VFMVF1`, the answer is the fund the platform calls that —
        which reaches the user under the name their certificate uses, `DCDS`.
        """
        found = [f.symbol for f in funds.search("VFMVF1")]
        assert found == ["DCDS"], found

    def test_an_exact_public_code_comes_first(self):
        found = [f.symbol for f in funds.search("VNDAF")]
        assert found[0] == "VNDAF", found

    def test_an_empty_query_asks_for_nothing(self):
        assert funds.search("   ") == []

    def test_the_catalogue_is_fetched_once_for_many_keystrokes(self, monkeypatch):
        calls = {"n": 0}

        def counting():
            calls["n"] += 1
            from tests.conftest import fake_fund_catalogue

            return fake_fund_catalogue()

        monkeypatch.setattr(funds, "_fetch_catalogue", counting)
        funds.forget_catalogue()

        for _ in range(5):
            funds.search("VNDAF")
        assert calls["n"] == 1, "the catalogue was fetched once per search"

    def test_a_request_for_a_fresh_catalogue_ignores_the_cache(self, monkeypatch):
        calls = {"n": 0}

        def counting():
            calls["n"] += 1
            from tests.conftest import fake_fund_catalogue

            return fake_fund_catalogue()

        monkeypatch.setattr(funds, "_fetch_catalogue", counting)
        funds.forget_catalogue()

        funds.catalogue()
        funds.catalogue(fresh=True)
        assert calls["n"] == 2


class TestTheDateHelpers:
    def test_fmarket_timestamps_become_dates(self):
        assert funds._date_from_epoch_ms(1_791_478_800_000) == "2026-10-08"

    def test_a_missing_timestamp_is_none_rather_than_today(self):
        assert funds._date_from_epoch_ms(None) is None
        assert funds._date_from_epoch_ms(0) is None
        assert funds._date_from_epoch_ms("nonsense") is None

    def test_the_nav_date_prefers_the_field_that_means_it(self):
        # updateAt is when the record was touched and can be months out of
        # date while the NAV is from yesterday.
        product = {
            "updateAt": 1_700_000_000_000,  # November 2023
            "extra": {"lastNAVDate": 1_791_478_800_000},  # October 2026
        }
        assert funds.nav_date(product) == "2026-10-08"

    def test_without_that_field_the_touch_date_is_used(self):
        assert funds.nav_date({"updateAt": 1_791_478_800_000}) == "2026-10-08"


class TestPricingAFundThroughTheRefresh:
    def test_a_fund_is_priced_even_though_yahoo_has_never_heard_of_it(self, db):
        db.add(
            models.Asset(
                symbol="VNDAF",
                kind="fund",
                name="VNDAF",
                quantity=1_000,
                cost_basis=20_000_000,
                currency="VND",
            )
        )
        db.commit()

        report = pricing.refresh_prices(db)
        assert report["ok"] is True
        assert report["refreshed"] == ["VNDAF"]

        row = db.get(models.PriceCache, "VNDAF")
        assert row is not None
        assert row.price == pytest.approx(18_049.76)
        assert row.currency == "VND"
        assert row.as_of == "2026-10-09"
        assert row.source == pricing.SOURCE_FUND

    def test_the_aliased_fund_is_priced_under_the_name_the_user_typed(self, db):
        db.add(
            models.Asset(
                symbol="DCDE",
                kind="fund",
                name="Quỹ cổ phiếu tập trung cổ tức DC",
                quantity=1_000,
                cost_basis=24_000_000,
                currency="VND",
            )
        )
        db.commit()
        pricing.refresh_prices(db)

        row = db.get(models.PriceCache, "DCDE")
        assert row is not None
        assert row.price == pytest.approx(24_582.29)

    def test_a_fund_is_valued_from_its_nav_like_any_other_position(self, db):
        from app import valuation

        db.add(
            models.Asset(
                symbol="VNDAF",
                kind="fund",
                name="VNDAF",
                quantity=1_000,
                cost_basis=17_000_000,
                currency="VND",
            )
        )
        db.commit()
        pricing.refresh_prices(db)

        asset = valuation.portfolio(db).assets[0]
        assert asset.value == pytest.approx(18_049_760)
        assert asset.value_base == pytest.approx(18_049_760)
        assert asset.price_as_of == "2026-10-09"

    def test_a_fund_whose_nav_cannot_be_fetched_is_reported_not_zeroed(self, db, monkeypatch):
        def explode(_symbol):
            raise OSError("Fmarket is down")

        monkeypatch.setattr(funds, "_fetch_product", explode)
        db.add(
            models.Asset(
                symbol="VNDAF", kind="fund", name="VNDAF",
                quantity=1_000, cost_basis=17_000_000, currency="VND",
            )
        )
        db.commit()

        report = pricing.refresh_prices(db)
        assert report["ok"] is False
        assert report["failed"][0]["symbol"] == "VNDAF"
        assert "fund:" in report["failed"][0]["error"]
        assert db.get(models.PriceCache, "VNDAF") is None

    def test_a_symbol_the_fund_source_priced_is_asked_there_first_next_time(self, db):
        """A fund does not become listed, and a stock does not start publishing
        a NAV, so the second refresh asks the source that answered first."""
        db.add(
            models.Asset(
                symbol="VNDAF", kind="fund", name="VNDAF",
                quantity=1, cost_basis=1, currency="VND",
            )
        )
        db.commit()
        pricing.refresh_prices(db)

        asked: list[str] = []
        from app import market

        original = market.quote

        def watched(symbol, **kwargs):
            asked.append(symbol)
            return original(symbol, **kwargs)

        monkeypatch_target = market.quote
        market.quote = watched  # type: ignore[assignment]
        try:
            pricing.refresh_prices(db)
        finally:
            market.quote = monkeypatch_target  # type: ignore[assignment]

        assert asked == [], "Yahoo was asked about a fund it can never price"

    def test_the_name_is_learned_from_the_source(self, db):
        db.add(
            models.Asset(
                symbol="VNDAF", kind="fund", name="VNDAF",
                quantity=1, cost_basis=1, currency="VND",
            )
        )
        db.commit()
        pricing.refresh_prices(db)

        instrument = db.get(models.Instrument, "VNDAF")
        assert instrument is not None
        assert instrument.kind == "fund"
        assert instrument.currency == "VND"
        assert "CHỦ ĐỘNG" in instrument.name


class TestTheSymbolPicker:
    def test_searching_a_fund_code_offers_it(self, client):
        body = client.get("/api/market/search", params={"q": "VNDAF"}).json()
        symbols = [s["symbol"] for s in body["suggestions"]]
        assert "VNDAF" in symbols
        hit = body["suggestions"][symbols.index("VNDAF")]
        assert hit["kind"] == "fund"
        assert hit["currency"] == "VND"

    def test_the_aliased_fund_is_offered_under_the_name_typed(self, client):
        body = client.get("/api/market/search", params={"q": "DCDE"}).json()
        assert body["suggestions"], "DCDE was not found at all"
        hit = body["suggestions"][0]
        assert hit["symbol"] == "DCDE"
        # Both names are shown, or the same fund appears twice under two names
        # and neither is recognisable as the other.
        assert "VFMVF4" in hit["name"]

    def test_a_fund_can_be_added_and_is_valued_immediately(self, client):
        created = client.post(
            "/api/assets",
            json={
                "symbol": "DCDE",
                "kind": "fund",
                "name": "Quỹ cổ phiếu tập trung cổ tức DC",
                "quantity": 1_000,
                "cost_basis": 24_000_000,
                "currency": "VND",
            },
        )
        assert created.status_code == 201
        body = created.json()
        assert body["price"] == pytest.approx(24_582.29)
        assert body["value_base"] == pytest.approx(24_582_290)
        assert body["price_as_of"] == "2026-10-08"
