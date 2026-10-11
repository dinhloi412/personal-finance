"""Closed positions over HTTP: the list, and forgetting one.

A sale is written by `POST /api/assets/{id}/sell`, which is where it happens.
It is readable here, and it is deletable here, for the same reason every other
table in this app is: a figure the user cannot inspect or correct is a figure
they have to trust. The Dashboard prints one realised total, so the rows behind
it have to be somewhere — and the day one of them is wrong, deleting it is the
way back.

Deleting a sale does NOT put the position back. The shares are gone and this app
has no way to know what they would be worth or what they cost; what is deleted
is the record of the trade, not the trade. The interface says so before it asks.
"""

from __future__ import annotations

from fastapi import APIRouter, status
from sqlalchemy import select

from app import fx, models, settings_store, valuation
from app.routers.deps import DbSession, get_or_404
from app.schemas import RealizedOut

router = APIRouter(prefix="/api/realized", tags=["realized"])


def _valued(session, row: models.Realized) -> RealizedOut:
    base = settings_store.base_currency(session)
    valued = valuation.value_sale(row, fx.Converter(session=session, base=base))
    return RealizedOut.model_validate(valued)


@router.get("", response_model=list[RealizedOut])
def list_realized(db: DbSession) -> list[RealizedOut]:
    """Every closed position, newest first — the same order the dashboard uses."""
    rows = db.execute(
        select(models.Realized).order_by(
            models.Realized.sold_on.desc(), models.Realized.id.desc()
        )
    ).scalars()
    return [_valued(db, row) for row in rows]


@router.delete("/{sale_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_realized(sale_id: int, db: DbSession) -> None:
    """Forget one recorded sale, for a trade entered by mistake."""
    row = get_or_404(db, models.Realized, sale_id, "Sale")
    db.delete(row)
    db.commit()
