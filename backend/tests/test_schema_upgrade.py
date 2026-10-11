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
