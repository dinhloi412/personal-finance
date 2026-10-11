"""An optional demo portfolio, for trying the app without typing anything in.

Used by `start.sh --demo`. It writes only into an empty database and only ever
against the file the caller pointed `DATABASE_URL` at, so it can never touch
the user's own `data.db`.

The holdings are real symbols, chosen to exercise every branch the app has:
two US positions, two Vietnamese stocks, an ETF, a crypto pair, and cash in
both currencies. Everything in the demo is quoted in VND or USD, because that
is what this app can total; a position quoted in anything else is reported but
deliberately not converted, which is a rule the tests cover rather than a thing
to hand a first-time user.
"""

from __future__ import annotations

import sys

from app import models, pricing
from app.database import SessionLocal, init_db

DEMO_ASSETS = [
    # symbol, kind, name, quantity, cost basis (total), currency of the cost
    ("AAPL", "stock", "Apple Inc.", 25, 4_000.0, "USD"),
    ("VIC.VN", "stock", "Vingroup JSC", 2_000, 130_000_000.0, "VND"),
    ("FPT.VN", "stock", "FPT Corporation", 500, 45_000_000.0, "VND"),
    ("VOO", "fund", "Vanguard S&P 500 ETF", 12, 6_500.0, "USD"),
    ("BTC-USD", "crypto", "Bitcoin", 0.15, 6_000.0, "USD"),
]

DEMO_CASH = [
    ("Vietcombank", "VND", 85_000_000.0),
    ("Techcombank", "VND", 40_000_000.0),
    ("Wise", "USD", 2_400.0),
]


def is_empty(session) -> bool:
    return (
        session.query(models.Asset).count() == 0
        and session.query(models.CashAccount).count() == 0
    )


def seed(*, force: bool = False) -> bool:
    """Write the demo portfolio. Returns False if there was already data."""
    init_db()
    session = SessionLocal()
    try:
        if not force and not is_empty(session):
            print("This database already has data; leaving it alone.")
            return False

        for symbol, kind, name, quantity, cost, currency in DEMO_ASSETS:
            session.add(
                models.Asset(
                    symbol=symbol,
                    kind=kind,
                    name=name,
                    quantity=quantity,
                    cost_basis=cost,
                    currency=currency,
                )
            )
        for name, currency, balance in DEMO_CASH:
            session.add(
                models.CashAccount(name=name, currency=currency, balance=balance)
            )
        session.commit()

        print("Fetching prices and rates for the demo portfolio...")
        report = pricing.refresh_all(session)
        for failure in report["prices"]["failed"]:
            print(f"  could not price {failure['symbol']}: {failure['error']}")
        print(f"  priced: {', '.join(report['prices']['refreshed']) or 'nothing'}")
        print(f"  rates:  {'ok' if report['fx']['ok'] else report['fx']['error']}")
        print(f"Demo portfolio written: {len(DEMO_ASSETS)} positions, {len(DEMO_CASH)} cash accounts.")
        return True
    finally:
        session.close()


def main(argv: list[str]) -> int:
    force = "--force" in argv
    if "--if-missing" in argv and not force:
        # The start script's default: seed once, then never again.
        seed(force=False)
        return 0
    seed(force=force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
