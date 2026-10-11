"""An optional demo portfolio, for trying the app without typing anything in.

Used by `start.sh --demo`. It writes only into an empty database and only ever
against the file the caller pointed `DATABASE_URL` at, so it can never touch
the user's own `data.db`.

The holdings are real symbols, chosen to exercise every branch the app has:
two US positions, two Vietnamese stocks, an ETF, a crypto pair, cash in both
currencies, gold, term deposits in every state a term can be in, and one
position sold in part — because the realised figures only appear on the pages
once something has been sold, and a demo that hid them would be a demo of a
smaller app. Everything in the demo is quoted in VND or USD, because that is
what this app can total; a position quoted in anything else is reported but
deliberately not converted, which is a rule the tests cover rather than a thing
to hand a first-time user.
"""

from __future__ import annotations

import datetime
import sys

from app import cash, models, pricing, realized
from app.database import SessionLocal, init_db

DEMO_ASSETS = [
    # symbol, kind, name, quantity, cost basis (total), currency of the cost
    ("AAPL", "stock", "Apple Inc.", 25, 4_000.0, "USD"),
    ("VIC.VN", "stock", "Vingroup JSC", 2_000, 130_000_000.0, "VND"),
    ("FPT.VN", "stock", "FPT Corporation", 500, 45_000_000.0, "VND"),
    ("VOO", "fund", "Vanguard S&P 500 ETF", 12, 6_500.0, "USD"),
    # Two Vietnamese OPEN-ENDED funds, priced by NAV rather than by a market
    # close. Included because they are the one kind of holding Yahoo cannot
    # price, and a demo that only showed listed things would not show that the
    # app can handle them at all. `DCDE` is the name on the certificate and
    # Fmarket calls the same fund `VFMVF4`.
    ("VNDAF", "fund", "VNDAF", 5_000, 90_000_000.0, "VND"),
    ("DCDE", "fund", "Quỹ cổ phiếu tập trung cổ tức DC", 3_000, 75_000_000.0, "VND"),
    ("BTC-USD", "crypto", "Bitcoin", 0.15, 6_000.0, "USD"),
]

#: name, quantity, unit, product key, pricing, cost paid. The product key is the
#: goldshop's own line, which is what the price follows — `VANG MIENG SJC` is a
#: different price from `NHẪN TRÒN TRƠN`, which is the whole point of tracking
#: gold in Vietnam rather than tracking the world price.
DEMO_GOLD = [
    ("SJC 5 chỉ", 5.0, "chi", "vang-mieng-sjc-vang-sjc", "buy", 6_800_000.0),
    ("Nhẫn tròn trơn 2 lượng", 2.0, "luong", "nhan-tron-tron-vang-rong-thang-long", "buy", 26_000_000.0),
]

#: currency, balance, label — one row per currency, because that is what cash is
#: now: a balance in đồng and a balance in dollars, accumulated into. The pots
#: already exist by the time the demo runs (`init_db` makes them); the demo fills
#: them in rather than creating them.
DEMO_CASH = [
    ("VND", 125_000_000.0, "Vietcombank"),
    ("USD", 2_400.0, "Wise"),
]

#: name, currency, principal, annual rate, term in days. The three are the
#: three states a deposit can be in: running, just matured, and demand.
DEMO_DEPOSITS = [
    ("Vietcombank 12 tháng", "VND", 200_000_000.0, 5.2, 365, 95),
    ("Techcombank 6 tháng", "VND", 100_000_000.0, 4.8, 181, 190),
    ("Ví không kỳ hạn", "VND", 5_000_000.0, 0.5, None, 60),
]

#: One position is sold in the demo — symbol, units, and what came back — so
#: that the realised figures and the list of closed trades are not invisible
#: until the day someone happens to sell something. A PARTIAL sale on purpose:
#: selling the whole position would show a closed trade without the live one it
#: came out of, and the two belong side by side.
DEMO_SALE = ("FPT.VN", 200.0, 24_000_000.0)


def is_empty(session) -> bool:
    """True when there is nothing the user put there.

    The two cash pots do not count. They exist in every database the app opens,
    empty (`app.cash`), and a demo that refused to load because cash has a home
    would be refusing for a reason nobody typed in — so cash counts as data only
    once there is money or a note in it.
    """
    return (
        session.query(models.Asset).count() == 0
        and session.query(models.Deposit).count() == 0
        and session.query(models.Gold).count() == 0
        and session.query(models.Realized).count() == 0
        and session.query(models.CashMovement).count() == 0
        and not any(
            float(pot.balance or 0.0) != 0.0 or pot.note
            for pot in session.query(models.CashAccount).all()
        )
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
        for currency, balance, label in DEMO_CASH:
            pot = cash.pot(session, currency)
            if pot is None:  # pragma: no cover - `init_db` makes both
                continue
            pot.name = label
            pot.balance = balance

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
        for name, quantity, unit, product_key, price_basis, cost in DEMO_GOLD:
            session.add(
                models.Gold(
                    name=name,
                    currency="VND",
                    quantity=quantity,
                    unit=unit,
                    product_key=product_key,
                    pricing=price_basis,
                    cost_basis=cost,
                )
            )
        session.commit()

        # The sale goes through the same function the API uses, so the demo
        # cannot show a portfolio that the app itself could not have produced:
        # the cost released is proportional, and the position it came from is
        # reduced by exactly the quantity sold.
        symbol, units, proceeds = DEMO_SALE
        sold = session.query(models.Asset).filter_by(symbol=symbol).one()
        quote = session.get(models.PriceCache, symbol)
        realized.apply_sale(
            session,
            sold,
            quantity=units,
            proceeds=proceeds,
            proceeds_currency=(quote.currency if quote else None) or sold.currency,
            sold_on=(today - datetime.timedelta(days=7)).isoformat(),
            note="Bán một phần",
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
            f"{len(DEMO_CASH)} cash accounts, {len(DEMO_DEPOSITS)} term deposits, "
            f"{len(DEMO_GOLD)} gold holdings, 1 sale."
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
