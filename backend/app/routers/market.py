"""Feeds: searching for a symbol, and refreshing what is stored.

Two ideas kept apart here. `GET /api/market/search` answers a question about
the world; `POST /api/prices/refresh` changes what is stored about it. A search
that is down is a degraded form-filler, not a broken app, so it answers 200
with `degraded: true` and lets the user type the symbol they already know.
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Query
from sqlalchemy import select

from app import market, models, pricing, settings_store
from app.routers.deps import DbSession
from app.schemas import (
    FxRefreshOut,
    FxRow,
    MarketOut,
    PriceRefreshOut,
    PriceRow,
    RefreshAllOut,
    SearchOut,
    SuggestionOut,
)

router = APIRouter(prefix="/api", tags=["market"])


@router.get("/market/search", response_model=SearchOut)
def search_symbols(
    db: DbSession,
    q: str = Query(min_length=1, description="a name or a ticker"),
    kind: str | None = Query(default=None, description="crypto completes a bare ticker"),
) -> SearchOut:
    """Symbols and names matching `q`, best first.

    When the feed finds nothing (or is unreachable) and `q` looks like a ticker,
    the symbol itself is resolved directly, so `VIC.VN` and `BTC-USD` can be
    added even with search down.
    """
    suggestions: list[SuggestionOut] = []
    degraded = False

    try:
        suggestions = [
            SuggestionOut(**asdict(hit)) for hit in market.search(q) if hit.kind
        ]
    except market.MarketError:
        degraded = True

    if not suggestions:
        direct = market.lookup_symbol(q, kind=kind)
        if direct is not None:
            suggestions = [SuggestionOut(**asdict(direct))]

    return SearchOut(query=q, suggestions=suggestions, degraded=degraded)


@router.get("/market", response_model=MarketOut)
def read_market(db: DbSession) -> MarketOut:
    """Everything cached: quotes with their close dates, rates with their day."""
    prices = [
        PriceRow.model_validate(row, from_attributes=True)
        for row in db.execute(
            select(models.PriceCache).order_by(models.PriceCache.symbol)
        ).scalars()
    ]
    base = settings_store.base_currency(db)
    rates = [
        FxRow.model_validate(row, from_attributes=True)
        for row in db.execute(
            select(models.FxRate)
            .where(models.FxRate.base == base)
            .order_by(models.FxRate.currency, models.FxRate.as_of.desc())
        ).scalars()
    ]
    return MarketOut(base_currency=base, prices=prices, rates=rates)


@router.get("/prices", response_model=list[PriceRow])
def list_prices(db: DbSession) -> list[PriceRow]:
    return [
        PriceRow.model_validate(row, from_attributes=True)
        for row in db.execute(
            select(models.PriceCache).order_by(models.PriceCache.symbol)
        ).scalars()
    ]


@router.post("/prices/refresh", response_model=PriceRefreshOut)
def refresh_prices(db: DbSession) -> PriceRefreshOut:
    """Fetch a quote for every symbol held. Failures are reported per symbol."""
    return PriceRefreshOut.model_validate(pricing.refresh_prices(db))


@router.get("/fx", response_model=list[FxRow])
def list_fx(db: DbSession) -> list[FxRow]:
    base = settings_store.base_currency(db)
    return [
        FxRow.model_validate(row, from_attributes=True)
        for row in db.execute(
            select(models.FxRate)
            .where(models.FxRate.base == base)
            .order_by(models.FxRate.currency, models.FxRate.as_of.desc())
        ).scalars()
    ]


@router.post("/fx/refresh", response_model=FxRefreshOut)
def refresh_fx(db: DbSession) -> FxRefreshOut:
    """Fetch today's rates for the base in force."""
    return FxRefreshOut.model_validate(pricing.refresh_fx(db))


@router.post("/refresh", response_model=RefreshAllOut)
def refresh_all(db: DbSession) -> RefreshAllOut:
    """Quotes and rates in one call — what the Refresh button in the header does."""
    return RefreshAllOut.model_validate(pricing.refresh_all(db))
