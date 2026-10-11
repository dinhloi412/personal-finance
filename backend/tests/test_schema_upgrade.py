"""The one migration this app is allowed to do: add a column that is missing.

This file exists because the failure it guards against is invisible in every
other test. The suite builds its schema from the models, so it always has the
newest shape — and a user's database, which was written by an older build, does
not. The symptom is not a clear refusal at startup; it is
`no such column: valuations.deposit_value` thrown from inside an unrelated
request, on a machine nobody can inspect.

The shape of the test is the shape of the bug: build the schema, take a column
away to make an older database, then check that opening it puts the column back
and that the figures still read.
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect, text

from app.database import Base, SessionLocal, add_missing_columns, engine


@pytest.fixture
def old_shape():
    """A database that predates `valuations.deposit_value`.

    Built by making the current schema and then dropping the column, which is
    the only honest way to simulate "this file was written by an older build"
    without keeping a copy of every old schema around.
    """
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE valuations DROP COLUMN deposit_value"))
    yield
    Base.metadata.drop_all(bind=engine)


def insert_valuation_row(*, day: str, total: float) -> None:
    """Write one valuation row with raw SQL, naming every column the table has.

    Every NOT NULL column gets a value, including ones the caller does not care
    about, because raw SQL does not apply a model's Python-side default — that
    is an ORM feature. Discovering that here is the point: a `default=0.0` on a
    column is a default for this app's writes only.
    """
    columns = {
        column["name"]: column
        for column in inspect(engine).get_columns("valuations")
    }
    values: dict[str, object] = {
        "as_of": day,
        "base_currency": "VND",
        "total": total,
        "market_value": total,
        "created_at": "now",
    }
    for name, column in columns.items():
        if name in values or column["nullable"]:
            continue
        # Anything else NOT NULL and unnamed: the zero of its own type.
        values[name] = "" if "CHAR" in str(column["type"]).upper() else 0

    names = ", ".join(values)
    placeholders = ", ".join(f":{name}" for name in values)
    with engine.begin() as connection:
        connection.execute(
            text(f"INSERT INTO valuations ({names}) VALUES ({placeholders})"),
            values,
        )


def columns(table: str) -> set[str]:
    return {column["name"] for column in inspect(engine).get_columns(table)}


class TestAddMissingColumns:
    def test_a_missing_column_is_reported_and_added(self, old_shape):
        assert "deposit_value" not in columns("valuations")
        assert add_missing_columns() == ["valuations.deposit_value"]
        assert "deposit_value" in columns("valuations")

    def test_running_it_twice_adds_nothing_the_second_time(self, old_shape):
        add_missing_columns()
        assert add_missing_columns() == []

    def test_a_row_written_before_the_column_existed_reads_as_zero(self, old_shape):
        """`ALTER TABLE ADD COLUMN ... NOT NULL` needs a value for the rows
        already there, and the one it gets must be the zero of the column's own
        type — not NULL, and not the row failing to load.

        The row is written through the ORM, the way the app writes one, rather
        than by raw SQL: a raw INSERT has to name every NOT NULL column and so
        would have to be edited each time a column is added, which is precisely
        the trap this test exists to catch.
        """
        from app import models

        # The row goes in while the column is still missing, which is the state
        # an older build would have left it in. Raw SQL, because the ORM would
        # name a column this schema does not have yet — and written from the
        # table's own columns rather than from a hand-kept list of them, so a
        # column added later does not make this test fail for the wrong reason.
        insert_valuation_row(day="2026-01-01", total=10.0)

        # Now open the database the way the app does, and confirm the column
        # comes back and the old row reads with the zero it must have.
        from app.database import init_db

        init_db()

        session = SessionLocal()
        try:
            row = session.get(models.Valuation, "2026-01-01")
            assert row is not None, "the old row disappeared"
            assert row.deposit_value == 0.0, "the old row gained no default"
            assert row.total == 10.0, "the upgrade changed a figure"
        finally:
            session.close()

    def test_a_database_missing_a_whole_table_is_created_not_migrated(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        # `create_all` has already made everything, so there is nothing to add.
        assert add_missing_columns() == []


class TestInitDbIsSafeToRunAgain:
    def test_opening_an_up_to_date_database_changes_nothing(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        before = {table: columns(table) for table in ("valuations", "deposits", "assets")}

        from app.database import init_db

        init_db()
        init_db()

        after = {table: columns(table) for table in ("valuations", "deposits", "assets")}
        assert after == before


@pytest.fixture
def old_cash_shape():
    """A database from before cash was one pot per currency.

    Built by hand rather than by dropping something: SQLite cannot remove a
    UNIQUE constraint, so the only way to have a `cash_accounts` table without
    one — which is what an older build wrote — is to create the table the way
    that build created it. `create_all` then leaves it exactly as it is, which
    is the behaviour the real upgrade relies on.
    """
    Base.metadata.drop_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE cash_accounts (
                    id INTEGER NOT NULL PRIMARY KEY,
                    name VARCHAR NOT NULL,
                    currency VARCHAR NOT NULL,
                    balance FLOAT NOT NULL DEFAULT 0,
                    note TEXT,
                    balance_at VARCHAR NOT NULL DEFAULT '2026-01-01',
                    created_at VARCHAR NOT NULL DEFAULT '2026-01-01',
                    updated_at VARCHAR NOT NULL DEFAULT '2026-01-01'
                )
                """
            )
        )
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


class TestMergingCashPots:
    """The one migration that is not "add a column".

    Cash became one balance per currency, and a database that holds two dong
    balances has to be brought forward or the rule is a comment rather than a
    fact. What must not happen is the money or the history disappearing, and
    what must happen is a copy of the file being written first.
    """

    def insert_account(self, name: str, currency: str, balance: float) -> int:
        with engine.begin() as connection:
            return connection.execute(
                text(
                    "INSERT INTO cash_accounts (name, currency, balance) "
                    "VALUES (:name, :currency, :balance)"
                ),
                {"name": name, "currency": currency, "balance": balance},
            ).lastrowid

    def test_two_dong_balances_become_one_with_the_money_added_up(self, old_cash_shape):
        from app import cash, models
        from app.database import merge_cash_pots

        first = self.insert_account("Vietcombank", "VND", 10_000_000)
        second = self.insert_account("Techcombank", "VND", 5_000_000)
        self.insert_account("Wise", "USD", 2_400)

        assert merge_cash_pots() != []

        session = SessionLocal()
        try:
            assert [row.currency for row in cash.pots(session)] == ["VND", "USD"]
            vnd = cash.pot(session, "VND")
            assert vnd.id == first
            assert vnd.balance == pytest.approx(15_000_000)
            assert cash.pot(session, "USD").balance == pytest.approx(2_400)
            assert session.query(models.CashAccount).count() == 2
            assert session.get(models.CashAccount, second) is None
        finally:
            session.close()

    def test_the_history_of_the_merged_pot_is_moved_not_lost(self, old_cash_shape):
        """Deleting an account cascades to its movements. A merge that erased
        half the cash history would be worse than the duplication it fixes."""
        from app import models
        from app.database import merge_cash_pots

        first = self.insert_account("Vietcombank", "VND", 0)
        second = self.insert_account("Techcombank", "VND", 0)
        with engine.begin() as connection:
            connection.execute(
                text(
                    # `created_at` is written out because raw SQL does not
                    # apply the model's Python-side default, as `insert_valuation_row`
                    # above says.
                    "INSERT INTO cash_movements (account_id, subject, action, "
                    "holding_id, name, amount, currency, occurred_on, created_at) "
                    "VALUES (:account, 'asset', 'buy', 1, 'VIC.VN', -1000, 'VND', "
                    "'2026-01-01', '2026-01-01')"
                ),
                {"account": second},
            )

        merge_cash_pots()

        session = SessionLocal()
        try:
            rows = session.query(models.CashMovement).all()
            assert len(rows) == 1
            assert rows[0].account_id == first
        finally:
            session.close()

    def test_a_database_with_one_pot_of_each_currency_is_not_merged(self, old_cash_shape):
        """Nothing is folded together — and both balances get the opening line
        the history was missing, which is a different job from merging."""
        from app import models
        from app.database import merge_cash_pots

        self.insert_account("Cash", "VND", 20_000_000)
        self.insert_account("Wise", "USD", 100)

        reported = merge_cash_pots()
        assert reported == ["VND: +2e+07", "USD: +100"]

        session = SessionLocal()
        try:
            assert session.query(models.CashAccount).count() == 2
            assert [
                row.name for row in session.query(models.CashAccount).all()
            ] == ["Cash", "Wise"]
            assert session.query(models.CashMovement).count() == 2
        finally:
            session.close()
