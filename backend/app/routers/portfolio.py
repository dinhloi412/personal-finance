"""The portfolio: one total, its parts, and the history behind it.

This router is thin on purpose. All the arithmetic is in `app.valuation`, which
is the only module allowed to decide what a total means; here the job is to
turn that into JSON and to record a point in time when asked.
"""

from __future__ import annotations

from fastapi import APIRouter

from app import models, settings_store, valuation
from app.routers.deps import DbSession
from app.schemas import HistoryOut, PortfolioOut, ValuationPoint

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("", response_model=PortfolioOut)
def read_portfolio(db: DbSession) -> PortfolioOut:
    """Everything held, valued in the base currency in force right now."""
    return PortfolioOut.model_validate(valuation.portfolio(db).as_dict())


@router.get("/history", response_model=HistoryOut)
def read_history(db: DbSession) -> HistoryOut:
    """The recorded net-worth series, oldest first.

    Each point carries the base currency it was written in, because a point is
    a fact about a day, not a number to be re-expressed at today's rate.
    """
    return HistoryOut(
        base_currency=settings_store.base_currency(db),
        points=[ValuationPoint.model_validate(point) for point in valuation.history(db)],
    )


@router.post("/snapshot", response_model=ValuationPoint)
def write_snapshot(db: DbSession) -> ValuationPoint:
    """Record today's total, replacing today's point if there already is one."""
    row = valuation.write_snapshot(db)
    return ValuationPoint(
        as_of=row.as_of,
        base_currency=row.base_currency,
        total=row.total,
        market_value=row.market_value,
        cash_value=row.cash_value,
        cost_value=row.cost_value,
        unconverted_count=row.unconverted_count,
    )


@router.delete("/history/{as_of}", status_code=204)
def delete_point(as_of: str, db: DbSession) -> None:
    """Drop one recorded day, for a point written by mistake."""
    row = db.get(models.Valuation, as_of)
    if row is not None:
        db.delete(row)
        db.commit()
