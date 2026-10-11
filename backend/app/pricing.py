"""Refreshing: asking the feeds, storing what they say, and reporting what
happened per symbol.

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

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import fx, market, models

logger = logging.getLogger(__name__)


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
        try:
            priced = market.quote(symbol)
        except market.MarketError as cause:
            _record_failure(session, symbol, str(cause))
            failed.append({"symbol": symbol, "error": str(cause)})
            continue
        except Exception as cause:  # noqa: BLE001 — a refresh never raises out
            logger.exception("unexpected failure pricing %s", symbol)
            _record_failure(session, symbol, str(cause))
            failed.append({"symbol": symbol, "error": str(cause)})
            continue

        _store(session, priced)
        refreshed.append(symbol)

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


def _store(session: Session, priced: market.Quote) -> None:
    """Write a quote over the previous one for the same symbol."""
    row = session.get(models.PriceCache, priced.symbol)
    if row is None:
        row = models.PriceCache(
            symbol=priced.symbol,
            price=priced.price,
            currency=priced.currency,
            as_of=priced.as_of,
        )
        session.add(row)
    else:
        row.price = priced.price
        # A quote that arrives without a currency does not erase one we already
        # learned: the listing currency of a symbol does not change.
        row.currency = priced.currency or row.currency
        row.as_of = priced.as_of
        row.fetched_at = models.utcnow_iso()
    row.error = None
    _learn_instrument(session, priced)


def _record_failure(session: Session, symbol: str, error: str) -> None:
    """Keep the old price, note the new failure."""
    row = session.get(models.PriceCache, symbol)
    if row is not None:
        row.error = error
        row.fetched_at = models.utcnow_iso()


def _learn_instrument(session: Session, priced: market.Quote) -> None:
    """Remember the listing currency behind a symbol, once we know it.

    The registry is filled from the quote rather than from the user's form so
    that the currency a position is *valued* in comes from the exchange, not
    from a dropdown someone could get wrong.
    """
    if not priced.currency:
        return
    row = session.get(models.Instrument, priced.symbol)
    if row is None:
        row = models.Instrument(
            symbol=priced.symbol,
            name=priced.name or priced.symbol,
            kind=market.kind_for_quote_symbol(priced.symbol) or "stock",
            currency=priced.currency,
        )
        session.add(row)
    else:
        if priced.currency:
            row.currency = priced.currency
        if priced.name:
            row.name = priced.name
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
