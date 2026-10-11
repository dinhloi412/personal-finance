"""What everything is worth, in one currency, with the arithmetic shown.

This is the module the app exists for, and it has one governing rule: **a total
is a sum of conversions, never a sum across mixed units.** Every figure below
is turned into the base currency by `fx.Converter` before it is added to
anything, and anything that cannot be converted is excluded from the total and
listed separately.

What it produces for one position:

    value        quantity × price, in the quote's currency
    value_base   the above in the base   (None if it cannot be converted)
    cost_base    cost_basis in the base  (None if no cost was recorded)
    gain         value_base − cost_base  (None if either is missing)
    reason       why a number is missing, in words the UI can show

The `reason` field is the point. "Unpriced", "unsupported currency" and "no
cost recorded" are three different situations that would otherwise all render
as a dash, and a dash teaches the user nothing about what to do next.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import deposits, fx, models, settings_store
from app.money import (
    MARKET_KINDS,
    AssetKind,
    decimals_for,
    is_supported_currency,
)

# Reason codes, shared with the UI so both sides use one spelling.
REASON_UNPRICED = "unpriced"
REASON_NOT_CONVERTIBLE = "not_convertible"
REASON_NO_QUANTITY = "no_quantity"
REASON_NO_COST = "no_cost"


@dataclass
class ValuedAsset:
    """One position, priced and converted, with its working shown."""

    id: int
    symbol: str
    name: str
    kind: str
    quantity: float
    currency: str
    note: str | None

    price: float | None
    price_currency: str | None
    price_as_of: str | None
    price_fetched_at: str | None

    cost_basis: float | None
    value: float | None
    value_base: float | None
    cost_base: float | None
    gain: float | None
    gain_pct: float | None

    #: None when every figure is present; otherwise why one is missing.
    reason: str | None = None

    @property
    def counted(self) -> bool:
        """True if this position is inside the portfolio total."""
        return self.value_base is not None


@dataclass
class ValuedCash:
    """One cash balance, converted."""

    id: int
    name: str
    currency: str
    balance: float
    balance_at: str
    note: str | None
    value_base: float | None
    reason: str | None = None

    @property
    def counted(self) -> bool:
        return self.value_base is not None


@dataclass
class Portfolio:
    """The whole picture: a total, its parts, and what is missing from it."""

    base_currency: str
    total: float = 0.0
    market_value: float = 0.0
    cash_value: float = 0.0
    deposit_value: float = 0.0
    cost_base: float | None = 0.0
    gain: float | None = 0.0
    gain_pct: float | None = None
    assets: list[ValuedAsset] = field(default_factory=list)
    cash: list[ValuedCash] = field(default_factory=list)
    deposits: list[dict] = field(default_factory=list)
    by_kind: list[dict] = field(default_factory=list)
    by_currency: list[dict] = field(default_factory=list)
    unconverted: list[dict] = field(default_factory=list)
    rates: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "base_currency": self.base_currency,
            "total": self.total,
            "market_value": self.market_value,
            "cash_value": self.cash_value,
            "deposit_value": self.deposit_value,
            "cost_base": self.cost_base,
            "gain": self.gain,
            "gain_pct": self.gain_pct,
            "assets": [asdict(asset) for asset in self.assets],
            "cash": [asdict(account) for account in self.cash],
            "deposits": self.deposits,
            "by_kind": self.by_kind,
            "by_currency": self.by_currency,
            "unconverted": self.unconverted,
            "rates": self.rates,
            "counts": {
                "assets": len(self.assets),
                "cash": len(self.cash),
                "deposits": len(self.deposits),
                "unconverted": len(self.unconverted),
            },
        }


# --------------------------------------------------------------------------
# One position at a time
# --------------------------------------------------------------------------


def value_asset(
    asset: models.Asset,
    price: models.PriceCache | None,
    converter: fx.Converter,
) -> ValuedAsset:
    """Price one market position in the base currency.

    The currency that counts is the QUOTE's, not the position's: a fund bought
    through a USD account but listed in EUR is worth what the market says, in
    the market's currency, and converting from the position's currency would
    apply the wrong rate to the right number.
    """
    price_currency = (price.currency if price else None) or None
    value: float | None = None
    value_base: float | None = None
    reason: str | None = None

    if asset.quantity is None or asset.quantity == 0:
        reason = REASON_NO_QUANTITY
    elif price is None:
        reason = REASON_UNPRICED
    elif not is_supported_currency(price_currency):
        # A quote in a currency this app cannot convert is reported, not
        # guessed at: calling it the base would add francs to a dong total.
        value = float(asset.quantity) * float(price.price)
        reason = REASON_NOT_CONVERTIBLE
    else:
        value = float(asset.quantity) * float(price.price)
        value_base = converter.to_base(value, price_currency)
        if value_base is None:
            reason = REASON_NOT_CONVERTIBLE

    # The cost is in the position's own recorded currency, which is not
    # necessarily the quote's: what you paid is a fact about your account.
    if asset.cost_basis is None:
        cost_base: float | None = None
        cost_reason = REASON_NO_COST
    else:
        cost_base = converter.to_base(asset.cost_basis, asset.currency)
        cost_reason = None if cost_base is not None else REASON_NOT_CONVERTIBLE

    gain: float | None = None
    gain_pct: float | None = None
    if value_base is not None and cost_base is not None:
        gain = value_base - cost_base
        if cost_base:
            gain_pct = gain / cost_base * 100.0

    if reason is None:
        reason = cost_reason

    return ValuedAsset(
        id=asset.id,
        symbol=asset.symbol,
        name=asset.name,
        kind=asset.kind,
        quantity=float(asset.quantity or 0.0),
        currency=asset.currency,
        note=asset.note,
        price=float(price.price) if price else None,
        price_currency=price_currency,
        price_as_of=price.as_of if price else None,
        price_fetched_at=price.fetched_at if price else None,
        cost_basis=asset.cost_basis,
        value=value,
        value_base=value_base,
        cost_base=cost_base,
        gain=gain,
        gain_pct=gain_pct,
        reason=reason,
    )


def value_cash(account: models.CashAccount, converter: fx.Converter) -> ValuedCash:
    """Convert one cash balance. Cash is never "unpriced" — only unconvertible."""
    value_base = converter.to_base(account.balance, account.currency)
    return ValuedCash(
        id=account.id,
        name=account.name,
        currency=account.currency,
        balance=float(account.balance or 0.0),
        balance_at=account.balance_at,
        note=account.note,
        value_base=value_base,
        reason=None if value_base is not None else REASON_NOT_CONVERTIBLE,
    )


def value_term_deposit(
    row: models.Deposit,
    converter: fx.Converter,
    *,
    as_of: date | None = None,
) -> dict:
    """Compute one deposit's interest and express both figures in the base.

    The interest is computed first, in the deposit's own currency, and only
    then converted — never the other way round, which would apply a rate to the
    wrong number and call the answer interest.
    """
    computed = deposits.value_deposit(row, as_of=as_of).as_dict()
    value_base = converter.to_base(computed["value"], row.currency)
    interest_base = converter.to_base(computed["interest_accrued"], row.currency)
    computed["value_base"] = value_base
    computed["interest_base"] = interest_base
    computed["reason"] = None if value_base is not None else REASON_NOT_CONVERTIBLE
    return computed


# --------------------------------------------------------------------------
# The whole picture
# --------------------------------------------------------------------------


def portfolio(session: Session, *, base: str | None = None) -> Portfolio:
    """Value every position and every cash balance in one base currency."""
    base = base or settings_store.base_currency(session)
    converter = fx.Converter(session=session, base=base)

    prices = {
        row.symbol: row for row in session.execute(select(models.PriceCache)).scalars()
    }

    assets = [
        value_asset(asset, prices.get(asset.symbol), converter)
        for asset in session.execute(select(models.Asset).order_by(models.Asset.id)).scalars()
    ]
    cash = [
        value_cash(account, converter)
        for account in session.execute(
            select(models.CashAccount).order_by(models.CashAccount.id)
        ).scalars()
    ]
    terms = [
        value_term_deposit(row, converter)
        for row in session.execute(
            select(models.Deposit).order_by(models.Deposit.id)
        ).scalars()
    ]

    result = Portfolio(base_currency=base, assets=assets, cash=cash, deposits=terms)

    cost_of_what_is_counted = 0.0
    counted_cost = True
    for asset in assets:
        if asset.value_base is not None:
            result.market_value += asset.value_base
        if asset.value_base is None:
            result.unconverted.append(
                {
                    "kind": "asset",
                    "id": asset.id,
                    "label": f"{asset.symbol} — {asset.name}",
                    "reason": asset.reason,
                }
            )
        # The gain is only meaningful over the positions that were both priced
        # and costed. If any counted position has no cost, the portfolio-level
        # gain says so by being None rather than by being too large.
        if asset.value_base is not None:
            if asset.cost_base is None:
                counted_cost = False
            else:
                cost_of_what_is_counted += asset.cost_base

    for account in cash:
        if account.value_base is not None:
            result.cash_value += account.value_base
        else:
            result.unconverted.append(
                {
                    "kind": "cash",
                    "id": account.id,
                    "label": f"{account.name} ({account.currency})",
                    "reason": account.reason,
                }
            )

    for term in terms:
        if term["value_base"] is not None:
            result.deposit_value += term["value_base"]
        else:
            result.unconverted.append(
                {
                    "kind": "deposit",
                    "id": term["id"],
                    "label": f"{term['name']} ({term['currency']})",
                    "reason": term["reason"],
                }
            )

    result.total = result.market_value + result.cash_value + result.deposit_value

    # Gain is about the market positions, so cash is not in its cost base.
    if counted_cost and assets:
        result.cost_base = cost_of_what_is_counted
        result.gain = result.market_value - cost_of_what_is_counted
        result.gain_pct = (
            result.gain / cost_of_what_is_counted * 100.0
            if cost_of_what_is_counted
            else None
        )
    else:
        result.cost_base = cost_of_what_is_counted if counted_cost else None
        result.gain = None
        result.gain_pct = None

    result.by_kind = _by_kind(assets, cash, terms)
    result.by_currency = _by_currency(assets, cash, terms)
    result.rates = converter.report()
    return result


def _by_kind(
    assets: list[ValuedAsset],
    cash: list[ValuedCash],
    deposits: list[dict],
) -> list[dict]:
    """Value per kind, in a fixed order, including the empty ones.

    Empty kinds are kept: a pie chart that silently loses its "crypto" slice
    when crypto is worth nothing looks like a bug, and a legend that says 0 is
    information.
    """
    order: tuple[AssetKind, ...] = (*MARKET_KINDS, "cash", "deposit")
    totals: dict[str, float] = {kind: 0.0 for kind in order}
    counts: dict[str, int] = {kind: 0 for kind in order}

    for asset in assets:
        counts[asset.kind] = counts.get(asset.kind, 0) + 1
        if asset.value_base is not None:
            totals[asset.kind] = totals.get(asset.kind, 0.0) + asset.value_base
    for account in cash:
        counts["cash"] += 1
        if account.value_base is not None:
            totals["cash"] += account.value_base
    for term in deposits:
        counts["deposit"] += 1
        if term["value_base"] is not None:
            totals["deposit"] += term["value_base"]

    return [
        {"kind": kind, "value": totals[kind], "count": counts[kind]}
        for kind in order
    ]


def _by_currency(
    assets: list[ValuedAsset],
    cash: list[ValuedCash],
    deposits: list[dict],
) -> list[dict]:
    """How much of the portfolio is exposed to each currency.

    Each row carries BOTH the amount in its own currency (`amount`) and that
    amount in the base (`value_base`). Only the second may be compared with
    another row or summed: the first is the size of the exposure, which is a
    different question from how much of the total it is.
    """
    amount: dict[str, float] = {}
    converted: dict[str, float] = {}

    for asset in assets:
        code = asset.price_currency or asset.currency
        if not code:
            continue
        # What the position is exposed to is what it was bought for, in the
        # currency it is quoted in — using the two interchangeably would double
        # count a position whose account currency differs from its listing.
        amount[code] = amount.get(code, 0.0) + (asset.value or 0.0)
        converted[code] = converted.get(code, 0.0) + (asset.value_base or 0.0)

    for account in cash:
        code = account.currency
        amount[code] = amount.get(code, 0.0) + account.balance
        converted[code] = converted.get(code, 0.0) + (account.value_base or 0.0)

    for term in deposits:
        code = term["currency"]
        amount[code] = amount.get(code, 0.0) + term["value"]
        converted[code] = converted.get(code, 0.0) + (term["value_base"] or 0.0)

    return [
        {
            "currency": code,
            "amount": amount[code],
            "value_base": converted[code],
            "decimals": decimals_for(code),
        }
        for code in sorted(converted, key=lambda c: -converted[c])
    ]


# --------------------------------------------------------------------------
# History
# --------------------------------------------------------------------------


def write_snapshot(session: Session, *, day: str | None = None) -> models.Valuation:
    """Record today's total, replacing today's row if there is one.

    One row per day, overwritten rather than appended: a user who refreshes
    prices three times before lunch has one value for today, not three, and the
    chart does not grow a spike out of their diligence.
    """
    day = day or models.today_iso()
    picture = portfolio(session)
    row = session.get(models.Valuation, day)
    if row is None:
        row = models.Valuation(as_of=day, base_currency=picture.base_currency, total=0.0)
        session.add(row)
    row.base_currency = picture.base_currency
    row.total = picture.total
    row.market_value = picture.market_value
    row.cash_value = picture.cash_value
    row.deposit_value = picture.deposit_value
    row.cost_value = picture.cost_base
    row.unconverted_count = len(picture.unconverted)
    session.commit()
    return row


def history(session: Session, *, limit: int = 365) -> list[dict]:
    """The recorded series, oldest point first, each in its own base.

    Points written in another base are returned with that base rather than
    converted: converting them at today's rate would turn a currency's move
    into the appearance of performance.
    """
    rows = list(
        session.execute(
            select(models.Valuation)
            .order_by(models.Valuation.as_of.desc())
            .limit(limit)
        ).scalars()
    )
    rows.reverse()
    return [
        {
            "as_of": row.as_of,
            "base_currency": row.base_currency,
            "total": row.total,
            "market_value": row.market_value,
            "cash_value": row.cash_value,
            "deposit_value": row.deposit_value,
            "cost_value": row.cost_value,
            "unconverted_count": row.unconverted_count,
        }
        for row in rows
    ]
