"""What the demo portfolio has to contain to be worth calling a demo.

The demo is the first thing anyone sees, and it is the only place where every
kind of holding appears at once. So it is checked rather than eyeballed: a
missing kind here is a feature nobody discovers exists.

The seed writes to whatever database it is pointed at, so this test points it
at the same in-memory database as the rest of the suite and never touches the
user's file.
"""

from __future__ import annotations

import datetime

import pytest

from app import seed


class TestTheDemoPortfolio:
    def test_it_is_written_into_an_empty_database(self, db):
        assert seed.is_empty(db) is True
        assert seed.seed() is True
        assert seed.is_empty(db) is False

    def test_it_never_overwrites_a_database_that_has_data(self, db):
        seed.seed()
        from app import models

        before = db.query(models.Asset).count()
        assert seed.seed() is False
        assert db.query(models.Asset).count() == before

    def test_it_holds_every_kind_the_app_can_track(self, db):
        seed.seed()
        from app import models

        kinds = {row.kind for row in db.query(models.Asset).all()}
        assert kinds == {"stock", "fund", "crypto"}
        assert db.query(models.CashAccount).count() > 0
        assert db.query(models.Deposit).count() > 0

    def test_it_holds_both_currencies(self, db):
        seed.seed()
        from app import models

        currencies = {row.currency for row in db.query(models.Asset).all()}
        currencies |= {row.currency for row in db.query(models.CashAccount).all()}
        assert currencies == {"VND", "USD"}

    def test_it_has_a_vietnamese_stock(self, db):
        """The whole point of the app for its user: a HOSE listing priced in
        dong, next to a US one priced in dollars."""
        seed.seed()
        from app import models

        assert any(
            row.symbol.endswith(".VN") for row in db.query(models.Asset).all()
        )

    def test_every_deposit_is_dated_relative_to_today(self, db):
        """So the demo always shows one running, one matured and one demand —
        every state the Savings page can render, on any day it is opened."""
        seed.seed()
        from app import models

        rows = db.query(models.Deposit).all()
        assert len(rows) == 3

        today = datetime.date.today().isoformat()
        running = [
            row
            for row in rows
            if row.maturity_date is not None and row.maturity_date >= today
        ]
        matured = [
            row
            for row in rows
            if row.maturity_date is not None and row.maturity_date < today
        ]
        demand = [row for row in rows if row.maturity_date is None]

        assert len(running) == 1, "one deposit should still be running"
        assert len(matured) == 1, "one deposit should have matured"
        assert len(demand) == 1, "one deposit should have no end date"

    def test_it_prices_what_it_can(self, db):
        """Through the fake market, so this asserts the wiring rather than
        Yahoo being up."""
        seed.seed()
        from app import models

        priced = {row.symbol for row in db.query(models.PriceCache).all()}
        symbols = {row.symbol for row in db.query(models.Asset).all()}
        assert symbols <= priced
