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

from sqlalchemy import create_engine, event
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
    """Create any missing tables. Idempotent, called once at startup."""
    from app import models  # noqa: F401  (registers the mappers)

    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
