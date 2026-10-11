"""Test fixtures.

Two rules the whole suite depends on:

1. **No network, ever.** `app.market.quote`, `app.market._fetch_search` and
   `app.fx._fetch_rates` are the only places in the app that touch the wire, and
   this file replaces all three with deterministic fakes. A test that reaches
   Yahoo is a test that fails on a plane.
2. **A fresh database per test.** An in-memory SQLite database, shared through
   a StaticPool (see `app/database.py`), built from the models and dropped with
   the test.

The fake feed trades at the same rate the app seeds a fresh database with
(26 000 VND per USD), so a test can never pass by quietly reading a placeholder
it did not ask for.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Make `app` importable when pytest is run from backend/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# The engine is created when `app.database` is imported, so the URL must be set
# first. `sqlite://` plus StaticPool gives every session the same in-memory
# database, which is what lets the app under test and the test itself see one
# schema.
os.environ["DATABASE_URL"] = "sqlite://"

from app import fx, market, models, pricing  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402

# --------------------------------------------------------------------------
# The fake market and the fake feed
# --------------------------------------------------------------------------

#: symbol -> (close, listing currency). `VWCE.DE` is quoted in a currency this
#: app deliberately cannot hold, which is how the "excluded, not guessed"
#: behaviour is tested without inventing a second fake.
#: The fake market quotes every symbol the demo portfolio holds, plus one in a
#: currency this app cannot convert — which is how the "excluded, not guessed"
#: path is tested without a second fake.
QUOTES: dict[str, tuple[float, str]] = {
    "AAPL": (200.0, "USD"),
    "VIC.VN": (100_000.0, "VND"),
    "FPT.VN": (60_000.0, "VND"),
    "VOO": (700.0, "USD"),
    "BTC-USD": (50_000.0, "USD"),
    "VWCE.DE": (100.0, "EUR"),
}

#: What the fake feed publishes: units of each currency per 1 USD.
#:
#: 26 000 is the real-world magnitude, which keeps the fake feed and the seed
#: rate the same number: a test that forgot to refresh cannot pass by accident.
FEED_FROM_USD = {"VND": 26_000.0, "USD": 1.0}


def fake_quote(symbol: str, *, name: str | None = None) -> market.Quote:
    """A quote from `QUOTES`, dated the same day for every symbol."""
    cleaned = market.normalise_symbol(symbol)
    if cleaned not in QUOTES:
        raise market.MarketError(f"no quote for {cleaned}")
    price, currency = QUOTES[cleaned]
    return market.Quote(
        symbol=cleaned,
        price=price,
        currency=currency,
        as_of="2026-01-15",
        name=name or cleaned,
    )


def fake_search(query: str, limit: int = 12) -> list[dict]:
    """Yahoo-shaped search rows, including one kind this app cannot hold."""
    rows = [
        {
            "symbol": "AAPL",
            "longname": "Apple Inc.",
            "quoteType": "EQUITY",
            "exchDisp": "NASDAQ",
            "score": 100.0,
        },
        {
            "symbol": "VIC.VN",
            "longname": "Vingroup JSC",
            "quoteType": "EQUITY",
            "exchDisp": "HOSE",
            "score": 50.0,
        },
        {
            # An index cannot be held, so it must never reach a portfolio.
            "symbol": "^GSPC",
            "longname": "S&P 500",
            "quoteType": "INDEX",
            "score": 10.0,
        },
    ]
    needle = query.strip().lower()
    return [
        row
        for row in rows
        if needle in row["symbol"].lower() or needle in row["longname"].lower()
    ]


def fake_feed(base: str) -> dict:
    """The FX feed's answer: units of each currency per 1 `base`."""
    if base == "USD":
        return {"result": "success", "rates": dict(FEED_FROM_USD)}
    if base == "VND":
        return {
            "result": "success",
            "rates": {"USD": 1.0 / FEED_FROM_USD["VND"], "VND": 1.0},
        }
    raise RuntimeError(f"the feed does not publish {base}")


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Replace every outbound call with a fake, for every test in the suite."""
    monkeypatch.setattr(market, "quote", fake_quote)
    monkeypatch.setattr(market, "_fetch_search", fake_search)
    monkeypatch.setattr(fx, "_fetch_rates", fake_feed)
    yield


@pytest.fixture
def offline(monkeypatch):
    """A fresh database with NO feed: only the hard-coded placeholder.

    This is the state of a laptop on a plane, and the app has to be usable in
    it — visibly, with every rate that came from the placeholder labelled.
    """
    def unreachable(_base):
        raise OSError("the network is a lie")

    monkeypatch.setattr(fx, "_fetch_rates", unreachable)

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        for base in ("VND", "USD"):
            fx.seed_rates(session, base)
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    """A fresh in-memory schema per test, with the seed rate already in it."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        for base in ("VND", "USD"):
            fx.seed_rates(session, base)
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db):
    """A TestClient sharing the test's session.

    The app's `get_db` dependency is overridden so the request handlers and the
    test look at the same in-memory database.
    """
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app

    def override():
        yield db

    app.dependency_overrides[get_db] = override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def held(db):
    """A small portfolio, already priced.

    Two positions and two cash balances, in both currencies, so that a total
    which forgot to convert one of them cannot accidentally come out right.
    """
    db.add(
        models.Asset(
            symbol="AAPL",
            kind="stock",
            name="Apple Inc.",
            quantity=10,
            cost_basis=1_500.0,  # USD
            currency="USD",
        )
    )
    db.add(
        models.Asset(
            symbol="VIC.VN",
            kind="stock",
            name="Vingroup JSC",
            quantity=100,
            cost_basis=9_000_000.0,  # VND
            currency="VND",
        )
    )
    db.add(models.CashAccount(name="Vietcombank", currency="VND", balance=50_000_000.0))
    db.add(models.CashAccount(name="Wise USD", currency="USD", balance=1_000.0))
    db.commit()
    pricing.refresh_prices(db)
    return db
