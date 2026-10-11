"""Closing a position: what went out, and what it cost to let it go.

This module owns one decision, and the whole file exists to make it explicit:
**a sale releases a proportional part of the position's cost basis, not a
recorded one.**

The reason is that a position stores one number — `cost_basis`, the total paid
— and not the individual purchases that made it up. So when half of a position
is sold, there is no fact of the form "these were the shares bought at 8 000":
the only honest answer is that half of what was paid has now been released.
That is average cost, and it is a *computation*, which is why it lives here
rather than in a router.

What this module deliberately does NOT decide is what the sale was worth in the
base currency. That is `app.valuation`, the one place allowed to convert
anything, and it derives those figures on read from the two amounts stored here.

The sale itself is written by `apply_sale`, which also answers the question the
user will ask next: does a position sold in full stay in the list at zero? It
does not — see the function.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app import models

#: How small a remaining quantity has to be before it is treated as none.
#:
#: Selling "everything" arrives here as a subtraction of two floats that were
#: meant to be equal, and float arithmetic is entitled to leave 5e-14 behind. A
#: position left at 5e-14 is not a rounding detail the user should see: it is a
#: row that would value at nothing and be reported as "khối lượng bằng 0" on the
#: dashboard. Quantities in this app span 0.0005 BTC to millions of đồng, so the
#: tolerance is deliberately far below anything a person would type.
NEGLIGIBLE = 1e-9


def proportional_cost(
    cost_basis: float | None, sold: float, held: float
) -> float | None:
    """The part of `cost_basis` that selling `sold` of `held` releases.

    None in, None out: a position with no recorded cost cannot have a part of
    that cost released, and inventing one from the current value is exactly the
    "movement since I wrote it down" that `models.Asset` refuses to call profit.

    A full sale returns the whole cost basis unchanged rather than
    `cost_basis * 1.0`, so that the number the user typed is the number that
    leaves the position — no multiplication for a float to round.
    """
    if cost_basis is None:
        return None
    if held <= NEGLIGIBLE or sold >= held:
        return float(cost_basis)
    if sold <= NEGLIGIBLE:
        return 0.0
    return float(cost_basis) * (sold / held)


def apply_sale(
    session: Session,
    asset: models.Asset,
    *,
    quantity: float,
    proceeds: float,
    proceeds_currency: str,
    sold_on: str,
    note: str | None = None,
) -> models.Realized:
    """Record a sale of `quantity` of `asset` and adjust what is held.

    The position is deleted when nothing is left of it. It is NOT kept at zero,
    and that is a decision with a visible consequence: a zero-quantity row has
    no `value_base`, so it would sit in the portfolio's `unconverted` list
    telling the user that a position they have already sold is "not counted"
    because it is missing a quantity. The record of the sale is `Realized`, and
    it is a better answer than a husk of a row.

    The caller commits. Every number the sale produces — the base-currency
    proceeds, the gain — is derived from this row on read, so there is nothing
    to keep in sync here.

    Raises `ValueError` for a sale that cannot happen (nothing held, nothing
    sold, more sold than is held); the router turns that into a refusal that
    says which of the three it was.
    """
    held = float(asset.quantity or 0.0)

    if held <= NEGLIGIBLE:
        raise ValueError(f"there is nothing left to sell: {asset.symbol} is at zero")
    if quantity <= 0:
        raise ValueError("quantity must be more than zero")
    if quantity > held + NEGLIGIBLE:
        raise ValueError(
            f"cannot sell {quantity:g} of {asset.symbol}: only {held:g} is held"
        )

    # A quantity a hair above what is held is a full sale, not an oversell: it
    # is what a form that pre-filled the held quantity can arrive as.
    sold = held if quantity > held else float(quantity)
    cost_removed = proportional_cost(asset.cost_basis, sold, held)

    row = models.Realized(
        symbol=asset.symbol,
        kind=asset.kind,
        name=asset.name or asset.symbol,
        quantity=sold,
        currency=asset.currency,
        cost_removed=cost_removed,
        proceeds=float(proceeds),
        proceeds_currency=proceeds_currency,
        sold_on=sold_on,
        note=note,
    )
    session.add(row)

    remaining = held - sold
    if remaining <= NEGLIGIBLE:
        session.delete(asset)
    else:
        asset.quantity = remaining
        # The cost basis is reduced by what the sale released, so that a
        # position sold down in pieces keeps answering "what is left worth
        # against what is left paid" rather than against the original total.
        asset.cost_basis = (
            None
            if asset.cost_basis is None or cost_removed is None
            else float(asset.cost_basis) - cost_removed
        )
        asset.updated_at = models.utcnow_iso()

    session.flush()
    return row
