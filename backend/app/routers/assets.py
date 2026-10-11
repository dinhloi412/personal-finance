"""Positions: create, read, update, delete, and value what is held.

Every response is a valued position, never a raw row. A row's `quantity` and
`cost_basis` mean nothing to a reader without a price and a base currency, and
the client that had to compute that itself would be a second place where the
conversion rule lives — the one that eventually adds dollars to dong.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, status
from sqlalchemy import select

from app import fx, models, pricing, settings_store, valuation
from app.routers.deps import DbSession, get_or_404
from app.schemas import AssetCreate, AssetOut, AssetUpdate
from app.valuation import REASON_UNPRICED

router = APIRouter(prefix="/api/assets", tags=["assets"])


def _valued(session, asset: models.Asset) -> AssetOut:
    """One position, priced from the cache and converted into the base."""
    base = settings_store.base_currency(session)
    converter = fx.Converter(session=session, base=base)
    price = session.get(models.PriceCache, asset.symbol)
    return AssetOut.model_validate(valuation.value_asset(asset, price, converter))


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
    db.commit()
    db.refresh(asset)

    if db.get(models.PriceCache, asset.symbol) is None:
        pricing.refresh_prices(db, [asset.symbol])

    return _valued(db, asset)


@router.get("/{asset_id}", response_model=AssetOut)
def read_asset(asset_id: int, db: DbSession) -> AssetOut:
    asset = get_or_404(db, models.Asset, asset_id, "Asset")
    return _valued(db, asset)


@router.patch("/{asset_id}", response_model=AssetOut)
def update_asset(asset_id: int, payload: AssetUpdate, db: DbSession) -> AssetOut:
    """Change any subset of a position's fields."""
    asset = get_or_404(db, models.Asset, asset_id, "Asset")
    fields = payload.model_dump(exclude_unset=True)

    if "symbol" in fields and fields["symbol"]:
        pricing.ensure_registered(
            db, fields["symbol"], fields.get("name") or asset.name, fields.get("kind") or asset.kind
        )
    for key, value in fields.items():
        if key == "name" and (value is None or not str(value).strip()):
            # A name of nothing is a name of the symbol: a row with no name is
            # unreadable, and refusing the whole edit over it would be worse.
            value = (fields.get("symbol") or asset.symbol).strip().upper()
        setattr(asset, key, value)

    asset.updated_at = models.utcnow_iso()
    db.commit()
    db.refresh(asset)
    return _valued(db, asset)


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(asset_id: int, db: DbSession) -> None:
    """Remove a position.

    The instrument and the cached quote stay: another position may share the
    symbol, and the quote is still a true statement about the market.
    """
    asset = get_or_404(db, models.Asset, asset_id, "Asset")
    db.delete(asset)
    db.commit()


@router.post("/{asset_id}/price", response_model=AssetOut)
def price_one(asset_id: int, db: DbSession) -> AssetOut:
    """Refresh this one position's quote, for the row that looks wrong."""
    asset = get_or_404(db, models.Asset, asset_id, "Asset")
    pricing.refresh_prices(db, [asset.symbol])
    priced = _valued(db, asset)
    if priced.price is None and priced.reason is None:
        priced.reason = REASON_UNPRICED
    return priced
