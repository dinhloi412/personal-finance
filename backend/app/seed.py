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

import datetime
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

#: name, currency, principal, annual rate, term in days. The three are the
#: three states a deposit can be in: running, just matured, and demand.
DEMO_DEPOSITS = [
    ("Vietcombank 12 tháng", "VND", 200_000_000.0, 5.2, 365, 95),
    ("Techcombank 6 tháng", "VND", 100_000_000.0, 4.8, 181, 190),
    ("Ví không kỳ hạn", "VND", 5_000_000.0, 0.5, None, 60),
]


def is_empty(session) -> bool:
    return (
        session.query(models.Asset).count() == 0
        and session.query(models.CashAccount).count() == 0
        and session.query(models.Deposit).count() == 0
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

        # A deposit's dates are relative to today, so the demo always shows one
        # running, one just matured and one with no end — which is every state
        # the Savings page can render.
        today = datetime.date.today()
        for name, currency, principal, rate, term, started_days_ago in DEMO_DEPOSITS:
            start = today - datetime.timedelta(days=started_days_ago)
            maturity = start + datetime.timedelta(days=term) if term else None
            session.add(
                models.Deposit(
                    name=name,
                    currency=currency,
                    principal=principal,
                    annual_rate=rate,
                    start_date=start.isoformat(),
                    maturity_date=maturity.isoformat() if maturity else None,
                    interest_mode="at_maturity",
                )
            )
        session.commit()

        print("Fetching prices and rates for the demo portfolio...")
        report = pricing.refresh_all(session)
        for failure in report["prices"]["failed"]:
            print(f"  could not price {failure['symbol']}: {failure['error']}")
        print(f"  priced: {', '.join(report['prices']['refreshed']) or 'nothing'}")
        print(f"  rates:  {'ok' if report['fx']['ok'] else report['fx']['error']}")
        print(
            f"Demo portfolio written: {len(DEMO_ASSETS)} positions, "
            f"{len(DEMO_CASH)} cash accounts, {len(DEMO_DEPOSITS)} term deposits."
        )
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
