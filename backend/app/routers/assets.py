"""Positions: create, read, update, delete, and value what is held.

Every response is a valued position, never a raw row. A row's `quantity` and
`cost_basis` mean nothing to a reader without a price and a base currency, and
the client that had to compute that itself would be a second place where the
conversion rule lives — the one that eventually adds dollars to dong.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, status
from sqlalchemy import select

from app import movements, fx, models, pricing, realized, settings_store, valuation
from app.routers.deps import DbSession, cash_report, get_or_404, refused
from app.schemas import (
    AssetCreate,
    AssetOut,
    AssetSellRequest,
    AssetUpdate,
    DeleteOut,
    RealizedOut,
)
from app.valuation import REASON_UNPRICED

router = APIRouter(prefix="/api/assets", tags=["assets"])

def _valued(session, asset: models.Asset) -> AssetOut:
    """One position, priced from the cache and converted into the base."""
    base = settings_store.base_currency(session)
    converter = fx.Converter(session=session, base=base)
    price = session.get(models.PriceCache, asset.symbol)
    return AssetOut.model_validate(valuation.value_asset(asset, price, converter))


def _valued_sale(session, row: models.Realized) -> RealizedOut:
    """One sale, converted into the base currency in force right now."""
    base = settings_store.base_currency(session)
    valued = valuation.value_sale(row, fx.Converter(session=session, base=base))
    return RealizedOut.model_validate(valued)


@router.get("", response_model=list[AssetOut])
def list_assets(
    db: DbSession,
    kind: str | None = Query(default=None, description="stock | fund | crypto"),
    q: str | None = Query(default=None, description="filter on symbol or name"),
) -> list[AssetOut]:
    """Every position, optionally filtered, always valued."""
    statement = select(models.Asset).order_by(models.Asset.symbol)
    if kind:
        statement = statement.where(models.Asset.kind == kind)
    if q:
        needle = f"%{q.strip().lower()}%"
        statement = statement.where(
            models.Asset.symbol.ilike(needle) | models.Asset.name.ilike(needle)
        )
    return [_valued(db, asset) for asset in db.execute(statement).scalars()]


@router.post("", response_model=AssetOut, status_code=status.HTTP_201_CREATED)
def create_asset(payload: AssetCreate, db: DbSession) -> AssetOut:
    """Add a position. The instrument registry is filled in if it is new.

    The first price is fetched best-effort: a network failure leaves the
    position stored and unpriced, which the response says with `reason`, rather
    than refusing to record something the user already owns.

    When the cash link is on, what the position cost leaves the chosen account
    in the same request — a purchase that recorded the shares but not the money
    would leave the two halves of one act telling different stories.
    """
    pricing.ensure_registered(db, payload.symbol, payload.name or "", payload.kind)
    asset = models.Asset(
        symbol=payload.symbol,
        kind=payload.kind,
        name=(payload.name or payload.symbol).strip(),
        quantity=payload.quantity,
        cost_basis=payload.cost_basis,
        currency=payload.currency,
        note=payload.note,
    )
    db.add(asset)
    # Flushed rather than committed: the cash row points at this position's id,
    # and both halves have to land together or not at all.
    db.flush()

    outcome = movements.spend(
        db,
        subject="asset",
        action="buy",
        name=asset.name,
        symbol=asset.symbol,
        holding_id=asset.id,
        amount=asset.cost_basis,
        currency=asset.currency,
        cash_amount=payload.cash_amount,
    )
    db.commit()
    db.refresh(asset)

    if db.get(models.PriceCache, asset.symbol) is None:
        pricing.refresh_prices(db, [asset.symbol])

    priced = _valued(db, asset)
    priced.cash = cash_report(db, outcome)
    return priced


@router.get("/{asset_id}", response_model=AssetOut)
def read_asset(asset_id: int, db: DbSession) -> AssetOut:
    asset = get_or_404(db, models.Asset, asset_id, "Asset")
    return _valued(db, asset)


@router.patch("/{asset_id}", response_model=AssetOut)
def update_asset(asset_id: int, payload: AssetUpdate, db: DbSession) -> AssetOut:
    """Change any subset of a position's fields.

    An edited cost basis moves the **difference** into or out of cash, because
    that is what changed about the money: the position was always worth what it
    was worth, but the record of what was paid for it was wrong by this much.
    Two cases deliberately do not move anything:

    - **clearing the cost** (to null). The money is still invested; the user has
      told the app they no longer know what it was, not that they got it back.
      Crediting the account would invent a movement that never happened.
    - **changing the quantity alone.** Correcting a typo in how many units are
      held is not a purchase. A real second purchase raises the cost basis too,
      and it is that field which moves the money.
    """
    asset = get_or_404(db, models.Asset, asset_id, "Asset")
    fields = payload.model_dump(exclude_unset=True)
    cash: movements.Outcome | None = None

    if "symbol" in fields and fields["symbol"]:
        pricing.ensure_registered(
            db, fields["symbol"], fields.get("name") or asset.name, fields.get("kind") or asset.kind
        )

    if "cost_basis" in fields:
        before = float(asset.cost_basis or 0.0)
        after = fields["cost_basis"]
        if after is not None and float(after) != before:
            outcome = movements.adjust(
                db,
                subject="asset",
                name=(fields.get("name") or asset.name) or asset.symbol,
                symbol=(fields.get("symbol") or asset.symbol),
                holding_id=asset.id,
                delta=float(after) - before,
                currency=(fields.get("currency") or asset.currency),
                    )
            cash = outcome

    for key, value in fields.items():
        if key == "name" and (value is None or not str(value).strip()):
            # A name of nothing is a name of the symbol: a row with no name is
            # unreadable, and refusing the whole edit over it would be worse.
            value = (fields.get("symbol") or asset.symbol).strip().upper()
        setattr(asset, key, value)

    asset.updated_at = models.utcnow_iso()
    db.commit()
    db.refresh(asset)

    updated = _valued(db, asset)
    if cash is not None:
        updated.cash = cash_report(db, cash)
    return updated


@router.delete("/{asset_id}", response_model=DeleteOut)
def delete_asset(asset_id: int, db: DbSession) -> DeleteOut:
    """Remove a position, giving back whatever cash it still had in it.

    The instrument and the cached quote stay: another position may share the
    symbol, and the quote is still a true statement about the market.

    What is given back is **not** the cost basis but the money the account
    actually paid and has not already had returned — see
    `movements.net_invested`. After a partial sale those two differ by the gain
    or loss already realised, and refunding the cost basis would put money into
    the account that never left it.

    A body is returned rather than a bare 204 because deleting is now two acts:
    the row goes, and money may come back. A client that could not tell whether
    the second one happened would have to guess about its own balance.
    """
    asset = get_or_404(db, models.Asset, asset_id, "Asset")
    outcome = movements.refund(
        db, subject="asset", holding_id=asset.id, name=asset.name, symbol=asset.symbol
    )
    db.delete(asset)
    db.commit()
    return DeleteOut(removed_id=asset_id, cash=cash_report(db, outcome))


@router.post("/{asset_id}/price", response_model=AssetOut)
def price_one(asset_id: int, db: DbSession) -> AssetOut:
    """Refresh this one position's quote, for the row that looks wrong."""
    asset = get_or_404(db, models.Asset, asset_id, "Asset")
    pricing.refresh_prices(db, [asset.symbol])
    priced = _valued(db, asset)
    if priced.price is None and priced.reason is None:
        priced.reason = REASON_UNPRICED
    return priced


@router.post("/{asset_id}/sell", response_model=RealizedOut)
def sell_asset(asset_id: int, payload: AssetSellRequest, db: DbSession) -> RealizedOut:
    """Sell part or all of a position, and keep the gain it locked in.

    Selling is the one action that destroys a figure the app cannot recompute:
    the position's cost basis. Delete a position by mistake and re-add it and
    the mistake is visible; sell it and the cost is gone for good. So the sale is
    written down in the same request, in `realized`, and the record survives the
    position — including when the position is sold in full and its row is
    removed.

    The money received goes into the account the user chose when the cash link
    is on, in the same request; with the link off it is recorded nowhere but on
    the sale, exactly as before. Either way the app never picks an account of
    its own accord — see `app.movements` for the two fields that decide it.
    """
    asset = get_or_404(db, models.Asset, asset_id, "Asset")

    # The market's currency for the symbol, so that what came back is expressed
    # the way the price was. Falls back to the position's own currency when the
    # symbol has never been quoted — the only other thing it could be.
    #
    # A quote in a currency this app cannot convert (a EUR listing, say) is
    # recorded and reported rather than refused here: the sale happened, and an
    # app that answered it with "I cannot write this down" would leave the user
    # holding a position they no longer own. `value_sale` converts what it can,
    # marks the rest `not_convertible`, and the realised totals say they do not
    # know instead of counting the proceeds as profit.
    quote = db.get(models.PriceCache, asset.symbol)
    proceeds_currency = (quote.currency if quote else None) or asset.currency

    try:
        row = realized.apply_sale(
            db,
            asset,
            quantity=payload.quantity,
            proceeds=payload.proceeds,
            proceeds_currency=proceeds_currency,
            # `today_iso` rather than `date.today()`: a sale and the valuation
            # snapshot taken in the same session must agree about which day it
            # is, and the snapshot is written in UTC.
            sold_on=payload.sold_on.isoformat() if payload.sold_on else models.today_iso(),
            note=payload.note,
        )
    except ValueError as cause:
        raise refused(str(cause)) from cause

    # The sale's own currency, not the position's: what came back is the market's
    # money, and it is the number the account is credited with.
    #
    # `holding_id` is the POSITION, not the sale: the flows of one position are
    # one account of what it has cost and returned, and that is what a delete
    # later gives back.
    outcome = movements.receive(
        db,
        subject="asset",
        action="sell",
        name=row.name,
        symbol=row.symbol,
        holding_id=asset_id,
        amount=row.proceeds,
        currency=row.proceeds_currency,
        cash_amount=payload.cash_amount,
        occurred_on=row.sold_on,
    )

    db.commit()
    db.refresh(row)
    sold = _valued_sale(db, row)
    sold.cash = cash_report(db, outcome)
    return sold
