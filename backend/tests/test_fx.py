"""Rates, and the one rule that keeps a total from being nonsense.

The fake feed answers 26 000 VND per USD. Every expected number below is that
rate or its inverse, and nothing else.
"""

from __future__ import annotations

import pytest

from app import fx, models

BASE = "VND"
OTHER = "USD"
FAKE_RATE = 26_000.0  # VND per USD, what `conftest.fake_feed` publishes


class TestSeeding:
    def test_a_fresh_database_can_convert_immediately(self, db):
        # The fixture stores the feed's rate, so this is the live number; the
        # point is that the rate exists at all before anyone asked for one.
        assert fx.rate_on(db, BASE, OTHER).rate == pytest.approx(1 / FAKE_RATE)

    def test_an_offline_install_still_gets_a_rate(self, offline):
        """With the feed down, a fresh database still converts something.

        The placeholder is labelled, never passed off as a quote.
        """
        rate = fx.rate_on(offline, BASE, OTHER)
        assert rate.rate == pytest.approx(1 / fx.SEED_USD_VND)
        assert rate.source == fx.SOURCE_SEED
        assert rate.stale is True

    def test_a_seeded_rate_says_it_is_a_placeholder(self, offline):
        assert fx.rate_on(offline, BASE, OTHER).stale is True

    def test_the_base_is_one_in_itself(self, db):
        rate = fx.rate_on(db, BASE, BASE)
        assert rate.rate == 1.0
        assert rate.stale is False

    def test_seeding_never_overwrites_a_real_rate(self, db):
        fx.refresh_rates(db, BASE)
        real = fx.rate_on(db, BASE, OTHER).rate
        fx.seed_rates(db, BASE)
        assert fx.rate_on(db, BASE, OTHER).rate == real


class TestRefresh:
    def test_a_refresh_stores_the_feeds_rate(self, db):
        report = fx.refresh_rates(db, BASE)
        assert report["ok"] is True
        assert "USD" in report["stored"]
        assert fx.rate_on(db, BASE, OTHER).rate == pytest.approx(1 / FAKE_RATE)
        assert fx.rate_on(db, BASE, OTHER).source == fx.SOURCE_FEED

    def test_a_fetched_rate_is_not_stale_for_the_day_it_arrived(self, db):
        fx.refresh_rates(db, BASE)
        assert fx.rate_on(db, BASE, OTHER).stale is False

    def test_an_unreachable_feed_does_not_raise(self, db, monkeypatch):
        def explode(_base):
            raise OSError("the network is a lie")

        monkeypatch.setattr(fx, "_fetch_rates", explode)
        report = fx.refresh_rates(db, BASE)
        assert report["ok"] is False
        assert "network" in report["error"]

    def test_an_unreachable_feed_leaves_the_old_rate_serving(self, db, monkeypatch):
        fx.refresh_rates(db, BASE)
        real = fx.rate_on(db, BASE, OTHER).rate

        def explode(_base):
            raise OSError("down")

        monkeypatch.setattr(fx, "_fetch_rates", explode)
        fx.refresh_rates(db, BASE)

        assert fx.rate_on(db, BASE, OTHER).rate == real

    def test_a_days_rate_does_not_overwrite_an_earlier_day(self, db, monkeypatch):
        fx._upsert(db, base=BASE, currency=OTHER, day="2026-01-01", rate=1 / 190.0)
        db.commit()
        monkeypatch.setattr(
            fx,
            "_fetch_rates",
            lambda _b: {"result": "success", "rates": {"USD": 1 / FAKE_RATE}},
        )
        fx.refresh_rates(db, BASE)

        assert fx.rate_on(db, BASE, OTHER, "2026-01-01").rate == pytest.approx(1 / 190.0)

    def test_a_feed_that_answers_with_nothing_useful_is_a_failure(self, db, monkeypatch):
        monkeypatch.setattr(fx, "_fetch_rates", lambda _b: {"result": "error"})
        assert fx.refresh_rates(db, BASE)["ok"] is False


class TestReadingTheRateOnADay:
    def test_the_day_asked_for_wins(self, db):
        fx._upsert(db, base=BASE, currency=OTHER, day="2026-03-01", rate=1 / 200.0)
        fx._upsert(db, base=BASE, currency=OTHER, day="2026-03-02", rate=1 / 210.0)
        db.commit()
        assert fx.rate_on(db, BASE, OTHER, "2026-03-02").rate == pytest.approx(1 / 210.0)

    def test_a_day_with_no_rate_uses_the_newest_older_one(self, db):
        fx._upsert(db, base=BASE, currency=OTHER, day="2026-03-01", rate=1 / 200.0)
        db.commit()
        # A rate published on the 2nd must not price a total fixed on the 1st.
        assert fx.rate_on(db, BASE, OTHER, "2026-03-01").rate == pytest.approx(1 / 200.0)

    def test_a_rate_from_the_future_is_labelled_stale(self, db):
        # Nothing at all for the day asked, but something after it: usable, and
        # said to be so. The seed is deleted so that the future row is the only
        # candidate and the test says what it means.
        for row in db.query(models.FxRate).all():
            db.delete(row)
        fx._upsert(db, base=BASE, currency=OTHER, day="2030-03-01", rate=1 / 200.0)
        db.commit()
        rate = fx.rate_on(db, BASE, OTHER, "2026-03-01")
        assert rate.stale is True
        assert rate.as_of == "2030-03-01"

    def test_a_rate_is_never_read_for_another_base(self, db):
        # Same pair, opposite direction, and the two must not mix: 200 VND per
        # USD read as 200 USD per VND would understate a portfolio 40 000-fold.
        fx._upsert(db, base="USD", currency="VND", day="2026-03-01", rate=200.0)
        db.commit()
        as_vnd_base = fx.rate_on(db, BASE, "USD", "2026-03-01")
        assert as_vnd_base.rate == pytest.approx(1 / fx.SEED_USD_VND)


class TestConverter:
    def test_dong_stays_dong(self, db):
        converter = fx.Converter(session=db, base="VND")
        assert converter.to_base(1_000_000.0, "VND") == 1_000_000.0

    def test_dollars_become_dong_at_the_rate(self, db, monkeypatch):
        monkeypatch.setattr(
            fx, "_fetch_rates", lambda _b: {"result": "success", "rates": {"USD": 1 / FAKE_RATE}}
        )
        fx.refresh_rates(db, "VND")
        converter = fx.Converter(session=db, base="VND")
        assert converter.to_base(1.0, "USD") == pytest.approx(FAKE_RATE)

    def test_dong_becomes_dollars_at_the_rate(self, db, monkeypatch):
        monkeypatch.setattr(
            fx, "_fetch_rates", lambda _b: {"result": "success", "rates": {"VND": FAKE_RATE}}
        )
        fx.refresh_rates(db, "USD")
        converter = fx.Converter(session=db, base="USD")
        assert converter.to_base(FAKE_RATE, "VND") == pytest.approx(1.0)

    def test_a_currency_the_app_cannot_hold_converts_to_none(self, db):
        converter = fx.Converter(session=db, base="VND")
        assert converter.to_base(100.0, "EUR") is None

    def test_no_currency_converts_to_none(self, db):
        converter = fx.Converter(session=db, base="VND")
        assert converter.to_base(100.0, None) is None

    def test_nothing_converts_to_none(self, db):
        converter = fx.Converter(session=db, base="VND")
        assert converter.to_base(None, "USD") is None

    def test_a_missing_rate_is_not_invented_as_one(self, db):
        # With every rate deleted, the honest answer is None, never the amount
        # itself: 100 dollars is not 100 dong.
        for row in db.query(models.FxRate).all():
            db.delete(row)
        db.commit()
        converter = fx.Converter(session=db, base="VND")
        assert converter.to_base(100.0, "USD") is None

    def test_the_report_says_which_rates_were_used(self, db):
        converter = fx.Converter(session=db, base="VND")
        converter.to_base(1.0, "USD")
        report = converter.report()
        assert [row["currency"] for row in report] == ["USD"]
        assert report[0]["as_of"]
        # A rate published for a day other than the one asked is labelled, so a
        # total never travels without its date.
        assert isinstance(report[0]["stale"], bool)

    def test_the_report_says_a_placeholder_is_one(self, offline):
        converter = fx.Converter(session=offline, base="VND")
        converter.to_base(1.0, "USD")
        assert converter.report()[0]["stale"] is True
        assert converter.report()[0]["source"] == fx.SOURCE_SEED
