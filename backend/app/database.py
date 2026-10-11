"""SQLite database configuration and session handling.

One file, `backend/data.db`, created on first start. The schema is created
straight from the SQLAlchemy metadata: this app has no migration history to
honour yet, and a tracker the user owns should be readable with `sqlite3`
rather than depend on a toolchain.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# backend/ = the parent of app/ (this file is backend/app/database.py)
BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BACKEND_DIR / "data.db"

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

# An in-memory SQLite URL gives every connection its OWN empty database, which
# is useless the moment a second connection opens — as FastAPI's threadpool
# does. `StaticPool` hands out one shared connection instead, so a test can run
# the whole app against `sqlite://` and still see its own schema.
_engine_kwargs: dict = {"connect_args": {"check_same_thread": False}}
if DATABASE_URL in ("sqlite://", "sqlite:///:memory:"):
    from sqlalchemy.pool import StaticPool

    _engine_kwargs["poolclass"] = StaticPool

engine = create_engine(DATABASE_URL, **_engine_kwargs)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_connection, _record) -> None:
    """Turn on foreign keys (SQLite has them off by default) and WAL.

    WAL lets a read (the dashboard) happen while a write (a price refresh) is
    in flight, which is the commonest overlap in this app.
    """
    if not isinstance(dbapi_connection, sqlite3.Connection):
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


@event.listens_for(SessionLocal, "before_flush")
def _register_instruments(session: Session, _flush_context, _instances) -> None:
    """Make sure every position about to be written has a registry row.

    A position points at a symbol, and the symbol points at a name and a
    currency. Rather than trust every caller to create the identity first — and
    turn a forgotten call into a foreign-key error at the least convenient
    moment — the identity is created here, from the position itself, on the way
    in. The first quote then refines the currency and the name.
    """
    from app import models

    pending = [
        obj for obj in session.new if isinstance(obj, models.Asset)
    ] + [
        obj
        for obj in session.dirty
        if isinstance(obj, models.Asset) and session.is_modified(obj, include_collections=False)
    ]
    for asset in pending:
        if not asset.symbol:
            continue
        if session.get(models.Instrument, asset.symbol) is not None:
            continue
        session.add(
            models.Instrument(
                symbol=asset.symbol,
                name=asset.name or asset.symbol,
                kind=asset.kind or "stock",
                currency=asset.currency,
            )
        )


def init_db() -> None:
    """Create any missing tables, and add any missing columns.

    Creating tables is not enough on its own. `create_all` makes a table that
    does not exist and does nothing at all to one that does, so the day a
    column is added to a model, every database that already exists keeps the
    old shape — and the failure is not a clear one. It is
    `no such column: valuations.deposit_value`, raised from inside an unrelated
    request, on a user's machine, in a file they cannot inspect.

    There is no migration history here on purpose: this app has one file, it is
    the user's, and the honest thing to do with it is add what is missing and
    touch nothing else. That covers the only kind of change this schema is
    allowed to make — a new column with a default.
    """
    from app import models  # noqa: F401  (registers the mappers)

    Base.metadata.create_all(bind=engine)
    add_missing_columns()
    merge_cash_pots()


def merge_cash_pots() -> list[str]:
    """Fold duplicate cash accounts into one pot per currency.

    The one migration in this app that is not "add a column". Cash used to be a
    list of named accounts; it is now one balance per currency (`app.cash`), and
    a database that holds two dong balances has to be brought forward or the
    rule is a comment rather than a fact.

    It is done here, with the rest of the startup work, and it is done *safely*:
    `app.cash.merge_duplicates` writes a copy of the database file beside it
    before it touches anything, moves the movement history onto the surviving
    account rather than letting it cascade away, and logs what it merged. The
    rule this file states above — a migration needs a copy of the file first —
    is kept, and the copy is the answer to "what did it do to my records".
    """
    from app import cash, models

    session = SessionLocal()
    try:
        merged = cash.merge_duplicates(session, source=database_path())
        cash.ensure_pots(session)
        # After the merge, not before: the merged balance is the one that has to
        # be accounted for.
        merged += cash.reconcile(session, source=database_path())
        return merged
    finally:
        session.close()


def database_path() -> Path | None:
    """The SQLite file this app is using, or None for an in-memory database.

    Read from the engine's URL rather than from `DEFAULT_DB_PATH`: a server
    started with `DATABASE_URL=sqlite:///demo.db` is using that file, and a
    backup written next to the wrong one is worse than no backup.
    """
    url = engine.url
    if url.database in (None, "", ":memory:"):
        return None
    return Path(url.database)


def add_missing_columns() -> list[str]:
    """Add columns the models declare and the database does not have.

    A column is only ever ADDED, never altered or dropped, and only when a
    default can be supplied for the rows already there. Anything else would be
    a migration, and a migration needs a copy of the file first — which is a
    conversation to have with the user, not a thing to do silently at startup.

    Returns what it added, which the tests assert on and the log records.

    The inspector is built INSIDE the transaction, after `create_all` may have
    made a table. An inspector built before that DDL answers from a cached view
    of the schema and reports the columns of a table that did not exist yet as
    already present — which is how a function whose whole job is to notice a
    missing column notices nothing.
    """
    added: list[str] = []

    with engine.begin() as connection:
        inspector = inspect(connection)
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            present = {column["name"] for column in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in present:
                    continue
                connection.execute(
                    text(
                        f"ALTER TABLE {table.name} ADD COLUMN "
                        f"{column.name} {_column_sql(column)}"
                    )
                )
                added.append(f"{table.name}.{column.name}")

    return added


def _column_sql(column) -> str:
    """The SQLite column definition to add `column` with.

    Quoted because a column may be named after a SQL keyword one day, and
    NOT NULL cannot be used without a default: SQLite refuses to add a NOT NULL
    column to a table that has rows, which is exactly the table this runs on.
    """
    from sqlalchemy import String
    from sqlalchemy.dialects import sqlite

    type_sql = column.type.compile(dialect=sqlite.dialect())
    default = column.default.arg if column.default is not None and not column.default.is_callable else None

    if default is not None:
        literal = f"'{default}'" if isinstance(column.type, String) else str(default)
        return f"{type_sql} NOT NULL DEFAULT {literal}"
    if not column.nullable:
        # No default to give, so the rows already there need something: the
        # zero of the column's own type. A numeric column added without a value
        # is 0, which is what "we did not have this figure" means in aggregate.
        zero = "''" if isinstance(column.type, String) else "0"
        return f"{type_sql} NOT NULL DEFAULT {zero}"
    return type_sql


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
