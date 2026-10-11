"""Gold over HTTP: the shop's price list, and the holdings that follow it.

Two halves, and they answer different questions:

- **`GET /api/gold/products`** is the shop: every line Bảo Tín Minh Châu
  publishes today, normalised to a price per chỉ. It is what the picker shows
  when someone is adding gold, and it is where a holding gets its `product_key`
  from. A shop that cannot be reached says so instead of answering with an
  empty list, because "no gold products exist" and "we could not ask" are
  different facts.
- **the holdings** are this app's records: a weight in a unit, a product line
  to follow, and whether to value it at what the shop pays (`buy`) or charges
  (`sell`).
"""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from app import movements, gold as gold_prices
from app import models, settings_store, valuation
from app.routers.deps import DbSession, cash_report, get_or_404, refused
from app.schemas import (
    DeleteOut,
    GoldCreate,
    GoldOut,
    GoldProductList,
    GoldProductOut,
    GoldUpdate,
)

router = APIRouter(prefix="/api/gold", tags=["gold"])


def _valued(session, row: models.Gold) -> GoldOut:
    """One holding, valued at today's shop price for its product line."""
    shop, error = valuation.gold_shop_prices()
    converter = _converter(session)
    return GoldOut.model_validate(
        valuation.value_gold_holding(
            row, converter, shop=shop.get(row.product_key), error=error
        )
    )


def _converter(session):
    from app import fx

    return fx.Converter(session=session, base=settings_store.base_currency(session))


def _product_out(product: gold_prices.GoldPrice) -> GoldProductOut:
    return GoldProductOut(
        key=product.key,
        name=product.name,
        buy=product.buy,
        sell=product.sell,
        unit=product.unit,
        updated_at=product.updated_at,
        updated_on=gold_prices.updated_on(product),
    )


@router.get("/products", response_model=GoldProductList)
def list_products(
    db: DbSession,
    q: str | None = Query(default=None, description="filter on the product name"),
    fresh: bool = Query(default=False, description="ignore the cached price list"),
) -> GoldProductList:
    """Every gold line the shop publishes, or why there are none."""
    try:
        products = (
            gold_prices.search(q, limit=50) if q else gold_prices.catalogue(fresh=fresh)
        )
        return GoldProductList(
            products=[_product_out(product) for product in products],
            source="Bảo Tín Minh Châu",
        )
    except gold_prices.GoldError as cause:
        return GoldProductList(
            products=[],
            degraded=True,
            error=str(cause),
            source="Bảo Tín Minh Châu",
        )


@router.get("", response_model=list[GoldOut])
def list_gold(db: DbSession) -> list[GoldOut]:
    from sqlalchemy import select

    return [
        _valued(db, row)
        for row in db.execute(select(models.Gold).order_by(models.Gold.id)).scalars()
    ]


@router.post("", response_model=GoldOut, status_code=status.HTTP_201_CREATED)
def create_gold(payload: GoldCreate, db: DbSession) -> GoldOut:
    """Add a gold holding.

    The product line is checked against the shop before the row is written: a
    holding that points at a key nothing publishes would be stored and then
    silently worth nothing, which is the failure this check exists to prevent.
    """
    try:
        # Checked before the row is written; the value is not needed, the
        # refusal is.
        gold_prices.find(payload.product_key)
    except gold_prices.GoldError as cause:
        raise refused(str(cause)) from cause

    row = models.Gold(
        name=payload.name.strip(),
        currency=payload.currency,
        quantity=payload.quantity,
        unit=payload.unit,
        product_key=payload.product_key,
        pricing=payload.pricing,
        cost_basis=payload.cost_basis,
        note=payload.note,
    )
    db.add(row)
    # Flushed, not committed: the cash row points at this holding's id, and the
    # two halves of one purchase have to land together or not at all.
    db.flush()

    outcome = movements.spend(
        db,
        subject="gold",
        action="buy",
        name=row.name,
        holding_id=row.id,
        amount=row.cost_basis,
        currency=row.currency,
        cash_amount=payload.cash_amount,
    )
    db.commit()
    db.refresh(row)

    holding = _valued(db, row)
    holding.cash = cash_report(db, outcome)
    return holding


@router.get("/{gold_id}", response_model=GoldOut)
def read_gold(gold_id: int, db: DbSession) -> GoldOut:
    return _valued(db, get_or_404(db, models.Gold, gold_id, "Gold holding"))


@router.patch("/{gold_id}", response_model=GoldOut)
def update_gold(gold_id: int, payload: GoldUpdate, db: DbSession) -> GoldOut:
    """Change a holding's weight, unit, product line or cost.

    An edited cost basis moves the difference into or out of cash, by the same
    rule as a position: the record of what was paid changed, so the money
    changed with it. Clearing the cost moves nothing — the gold is still
    owned — and changing the weight alone is a correction, not a purchase.
    """
    row = get_or_404(db, models.Gold, gold_id, "Gold holding")
    fields = payload.model_dump(exclude_unset=True)
    cash: movements.Outcome | None = None

    if "cost_basis" in fields:
        before = float(row.cost_basis or 0.0)
        after = fields["cost_basis"]
        if after is not None and float(after) != before:
            cash = movements.adjust(
                db,
                subject="gold",
                name=(fields.get("name") or row.name),
                holding_id=row.id,
                delta=float(after) - before,
                currency=(fields.get("currency") or row.currency),
                    )

    if "name" in fields and fields["name"]:
        fields["name"] = fields["name"].strip()

    if "product_key" in fields and fields["product_key"]:
        try:
            gold_prices.find(fields["product_key"])
        except gold_prices.GoldError as cause:
            raise refused(str(cause)) from cause

    for key, value in fields.items():
        setattr(row, key, value)

    row.updated_at = models.utcnow_iso()
    db.commit()
    db.refresh(row)

    updated = _valued(db, row)
    if cash is not None:
        updated.cash = cash_report(db, cash)
    return updated


@router.delete("/{gold_id}", response_model=DeleteOut)
def delete_gold(gold_id: int, db: DbSession) -> DeleteOut:
    """Remove a holding, giving back what it still had in a cash account."""
    row = get_or_404(db, models.Gold, gold_id, "Gold holding")
    outcome = movements.refund(
        db, subject="gold", holding_id=row.id, name=row.name
    )
    db.delete(row)
    db.commit()
    return DeleteOut(removed_id=gold_id, cash=cash_report(db, outcome))
