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

    def test_the_rows_already_there_get_the_default(self, old_shape):
        """`ALTER TABLE ADD COLUMN` with NOT NULL needs a value for existing
        rows, and the one it gets must be the zero of the column's own type."""
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO valuations "
                    "(as_of, base_currency, total, market_value, cash_value, "
                    " cost_value, unconverted_count, created_at) "
                    "VALUES ('2026-01-01', 'VND', 10.0, 10.0, 0.0, NULL, 0, 'now')"
                )
            )
        add_missing_columns()

        session = SessionLocal()
        try:
            from app import models

            row = session.get(models.Valuation, "2026-01-01")
            assert row is not None
            assert row.deposit_value == 0.0
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
