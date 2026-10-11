"""Refreshing: asking the feeds, storing what they say, and reporting what
happened per symbol.

**Two feeds, one question.** "What is this worth" has two answers in this app:
a market price for anything listed (Yahoo) and a NAV for an open-ended fund
(Fmarket). A fund certificate is not listed, so Yahoo will never price it — and
conversely, asking Fmarket about `AAPL` wastes a request on a definite no. The
order is therefore: try the source the symbol was priced from last time, then
the other one, then record the failure. That last part matters more than the
order: a symbol nobody can price must end up with its failure written against
it, not with a stale number silently reused as though it were today's.

A refresh is not a transaction. One unreachable listing must not roll back the
nineteen that answered, and one bad ticker must not turn into a 500. So this
module loops, catches per item, writes what it got, and returns a report the
user can read:

    {"ok": true, "refreshed": ["AAPL", "BTC-USD"], "failed": [{"symbol": ..., "error": ...}]}

The cached row is never deleted on failure — a stale price with its date beats
a blank cell — and the failure is recorded on the row so the UI can mark it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import funds, fx, market, models

logger = logging.getLogger(__name__)


#: Which feed priced a symbol, stored on its cache row. A short word rather
#: than a module path, because it is written into the database and read by a
#: human debugging a portfolio.
SOURCE_MARKET = "market"
SOURCE_FUND = "fund"


@dataclass(frozen=True)
class Priced:
    """What a cache row needs, from either feed.

    `market.Quote` says `price` and `funds.FundQuote` says `nav`, because a
    close and a net asset value are different facts with different names. This
    is where that difference stops: one store, one shape, no attribute that
    exists on only one of them.
    """

    symbol: str
    price: float
    currency: str | None
    as_of: str
    name: str | None = None


def _as_priced(quote) -> Priced:
    """Normalise either feed's quote into the shape the store writes."""
    price = getattr(quote, "price", None)
    if price is None:
        price = getattr(quote, "nav")
    return Priced(
        symbol=quote.symbol,
        price=float(price),
        currency=quote.currency,
        as_of=quote.as_of,
        name=getattr(quote, "name", None),
    )


def refresh_prices(session: Session, symbols: list[str] | None = None) -> dict:
    """Fetch and store a quote for every symbol asked for.

    With no argument, every symbol the user actually holds (plus any already in
    the cache, so a watch of a sold position still updates). Symbols are
    de-duplicated and never fetched twice in one pass.
    """
    wanted = symbols if symbols is not None else _held_symbols(session)
    seen: list[str] = []
    for symbol in wanted:
        cleaned = market.normalise_symbol(symbol)
        if cleaned and cleaned not in seen:
            seen.append(cleaned)

    refreshed: list[str] = []
    failed: list[dict] = []

    for symbol in seen:
        errors: list[str] = []

        for source, fetch in _sources_for(session, symbol):
            try:
                quote = fetch()
            except Exception as cause:  # noqa: BLE001 — a refresh never raises out
                errors.append(f"{source}: {cause}")
                continue

            store_quote(session, _as_priced(quote), source=source)
            refreshed.append(symbol)
            break
        else:
            # No source could price it. The failure is recorded against the
            # symbol so the interface can say which one, and any older price
            # stays where it is — dated, and therefore honest.
            message = "; ".join(errors) or "no source could price it"
            _record_failure(session, symbol, message)
            failed.append({"symbol": symbol, "error": message})

    session.commit()
    return {
        "ok": not failed,
        "refreshed": refreshed,
        "failed": failed,
        "asked": len(seen),
    }


def _held_symbols(session: Session) -> list[str]:
    held = list(
        session.execute(select(models.Asset.symbol).distinct()).scalars()
    )
    cached = list(session.execute(select(models.PriceCache.symbol)).scalars())
    return [*held, *cached]


def _sources_for(session: Session, symbol: str):
    """The feeds to try for `symbol`, most likely first.

    A symbol already priced by one source is tried there first, because the
    answer is known: a fund will not start being listed, and a stock will not
    start publishing a NAV. Trying the wrong one first costs a request and,
    worse, a delay on every refresh.
    """
    market_source = (SOURCE_MARKET, lambda: market.quote(symbol))
    fund_source = (SOURCE_FUND, lambda: funds.quote(symbol))

    row = session.get(models.PriceCache, symbol)
    if row is not None and row.source == SOURCE_FUND:
        return [fund_source, market_source]
    return [market_source, fund_source]


def store_quote(session: Session, quote, *, source: str) -> None:
    """Write a quote over the previous one for the same symbol.

    Both quote types carry the same four things — symbol, price, currency, the
    day the number is for — which is what makes one store enough for two feeds.
    """
    row = session.get(models.PriceCache, quote.symbol)
    if row is None:
        row = models.PriceCache(
            symbol=quote.symbol,
            price=quote.price,
            currency=quote.currency,
            as_of=quote.as_of,
        )
        session.add(row)
    else:
        row.price = quote.price
        # A quote that arrives without a currency does not erase one we already
        # learned: the currency of a symbol does not change.
        row.currency = quote.currency or row.currency
        row.as_of = quote.as_of
        row.fetched_at = models.utcnow_iso()
    row.source = source
    row.error = None
    _learn_instrument(session, quote, source=source)


def _record_failure(session: Session, symbol: str, error: str) -> None:
    """Keep the old price, note the new failure."""
    row = session.get(models.PriceCache, symbol)
    if row is not None:
        row.error = error
        row.fetched_at = models.utcnow_iso()


def _learn_instrument(session: Session, quote, *, source: str = SOURCE_MARKET) -> None:
    """Remember the name and currency behind a symbol, once we know them.

    Filled from the quote rather than from the user's form so that the currency
    a position is *valued* in comes from the source, not from a dropdown
    someone could get wrong. A fund's name is worth overwriting with its full
    one: `VNDAF` becomes "QUỸ ĐẦU TƯ CHỦ ĐỘNG VND", which is what the
    certificate says.
    """
    if not quote.currency:
        return
    kind = "fund" if source == SOURCE_FUND else (market.kind_for_quote_symbol(quote.symbol) or "stock")
    row = session.get(models.Instrument, quote.symbol)
    if row is None:
        row = models.Instrument(
            symbol=quote.symbol,
            name=quote.name or quote.symbol,
            kind=kind,
            currency=quote.currency,
        )
        session.add(row)
    else:
        if quote.currency:
            row.currency = quote.currency
        if quote.name:
            row.name = quote.name
        row.kind = kind
    row.updated_at = models.utcnow_iso()


def ensure_registered(session: Session, symbol: str, name: str, kind: str) -> models.Instrument:
    """Make sure a symbol has a registry row before an Asset points at it.

    Filled from what the user typed / the picker returned; the first quote then
    refines the currency and the name.
    """
    cleaned = market.normalise_symbol(symbol, kind)
    row = session.get(models.Instrument, cleaned)
    if row is None:
        row = models.Instrument(
            symbol=cleaned,
            name=name or cleaned,
            kind=kind,
            currency=market.currency_from_symbol(cleaned),
        )
        session.add(row)
        session.flush()
    return row


def refresh_fx(session: Session, base: str | None = None) -> dict:
    """Refresh the FX table for the base in force (or the one given)."""
    from app import settings_store

    code = base or settings_store.base_currency(session)
    return fx.refresh_rates(session, code)


def refresh_all_fx(session: Session) -> dict:
    """Refresh every base the user may read the portfolio in.

    Both, not only the one in force: the base is one click away on the
    dashboard. A database holding a rate for VND alone reads a USD valuation of
    a dong portfolio as nothing at all — every position unconvertible, the
    total zero, and no error to explain it.
    """
    results = {base: fx.refresh_rates(session, base) for base in fx.supported()}
    return {
        "ok": all(result["ok"] for result in results.values()),
        "bases": results,
        "error": next(
            (result["error"] for result in results.values() if not result["ok"]), None
        ),
        "stored": sorted({code for result in results.values() for code in result["stored"]}),
        "as_of": next(iter(results.values()))["as_of"],
    }


def refresh_all(session: Session) -> dict:
    """Prices and rates together, which is what the Refresh button means."""
    prices = refresh_prices(session)
    rates = refresh_all_fx(session)
    return {"prices": prices, "fx": rates}
