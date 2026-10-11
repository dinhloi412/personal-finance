"""Request and response shapes.

These are the contract. The frontend copy of these types is hand-written (see
`frontend/src/api/types.ts`) rather than generated, so the two files are meant
to be read side by side: if a field changes here and not there, TypeScript
fails the build, which is the point.

Two things are enforced here rather than in the database, because they are
rules about what a *request* may say:

- `currency` is `Literal["VND", "USD"]`. A tracker for two currencies that
  accepts a third has quietly become a tracker for one currency and some
  numbers that get added to it anyway.
- `kind` is `Literal["stock", "fund", "crypto"]`, and cash is not in it. Cash
  has its own endpoints and its own table.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app import movements, money

# The three aliases below are the same three closed sets as `app.money`'s, and
# they are cross-checked against it at import time: a `Literal` cannot be built
# from a variable in Python, so the only way to keep one definition is to make
# a disagreement impossible to miss. `tests/test_scope.py` asserts on the result.
assert money.CURRENCIES == ("VND", "USD")
assert money.LANGUAGES == ("vi", "en")
assert money.MARKET_KINDS == ("stock", "fund", "crypto")
assert money.SUBJECT_KINDS == ("asset", "gold", "deposit", "cash")
assert money.FLOW_ACTIONS == (
    "buy",
    "sell",
    "open",
    "close",
    "adjust",
    "refund",
    "in",
    "out",
)
assert movements.SKIP_CODES == (
    "link_off",
    "no_amount",
    "no_account",
    "no_rate",
    "nothing_paid",
)

Currency = Literal["VND", "USD"]
MarketKind = Literal["stock", "fund", "crypto"]
LanguageLiteral = Literal["vi", "en"]
SubjectKindLiteral = Literal["asset", "gold", "deposit", "cash"]
FlowActionLiteral = Literal[
    "buy", "sell", "open", "close", "adjust", "refund", "in", "out"
]
#: Why the cash side of a trade did nothing. Shared with `app.movements`; the
#: interface turns each code into a sentence about what to do next.
SkipCode = Literal["link_off", "no_amount", "no_account", "no_rate", "nothing_paid"]


# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------


class SettingsOut(BaseModel):
    base_currency: Currency
    language: LanguageLiteral
    #: Whether trades move money in and out of a cash account. Off by default:
    #: while the portfolio is being typed in, cash and holdings are two
    #: independent facts, and nothing moves until the user asks for it.
    cash_linked: bool
    supported_currencies: list[str]
    supported_kinds: list[str]
    supported_languages: list[str]
    #: Where the SQLite file lives, shown in Settings so the user can back it up.
    database_path: str
    version: str


class SettingsPatch(BaseModel):
    base_currency: Currency | None = None
    language: LanguageLiteral | None = None
    cash_linked: bool | None = None


class WipeOut(BaseModel):
    """What a wipe removed, per table, so the confirmation can say it plainly."""

    removed: dict[str, int]


# --------------------------------------------------------------------------
# The cash side of a trade
# --------------------------------------------------------------------------


class CashMoveRequest(BaseModel):
    """The cash side of a trade, as a client asks for it.

    Inherited by every payload that can move money, so the two fields are
    spelled the same everywhere and a new endpoint cannot invent a third name
    for them.

    The account is not a field. Cash is one pot per currency and the pot is
    picked by the trade's own currency, so there is nothing to choose and no way
    for the money to be recorded in the wrong pile.

    `cash_amount` is optional, and that is the design: with the cash link off it
    is ignored, and with it on it is an *override* of what the app would do on
    its own. Omitting it means "move what this trade is worth" — which, the pot
    being in the trade's currency, is the trade's own number to the last decimal.
    Sending it means "this is what actually left the account", the one figure
    only the user has: a fee, or a rate the bank applied.
    """

    #: Positive, in the pot's currency: the direction comes from the trade.
    cash_amount: float | None = Field(default=None, gt=0)


class CashMoveOut(CashMoveRequest):
    """What the cash side actually did, or why it did nothing.

    Returned beside the holding it belongs to, because a trade that moved
    someone's money has to say so in the same breath — and a trade that did
    *not* move it, when the user expected it to, has to say why.
    """

    moved: bool
    #: One of `money.SKIP_CODES` when nothing moved.
    skipped: SkipCode | None = None
    movement_id: int | None = None
    account_id: int | None = None
    account_name: str | None = None
    #: Signed, in `currency`: negative is money out of the account.
    amount: float | None = None
    currency: str | None = None
    #: The account's balance after the movement, so a client can show the
    #: result without asking again.
    balance: float | None = None


class DeleteOut(BaseModel):
    """What a delete did besides removing the row.

    Deleting a holding is now two acts when the cash link is on: the row goes,
    and the money the account still had in it comes back. A bare `204 No
    Content` would leave the client unable to tell whether the second one
    happened, which for a balance the user is looking at is not an acceptable
    thing to be unsure about.
    """

    removed_id: int
    cash: CashMoveOut


# --------------------------------------------------------------------------
# Assets (market positions)
# --------------------------------------------------------------------------


class AssetCreate(CashMoveRequest):
    symbol: str = Field(min_length=1, max_length=32)
    kind: MarketKind
    name: str | None = Field(default=None, min_length=1, max_length=200)
    quantity: float = Field(ge=0)
    cost_basis: float | None = Field(default=None, ge=0)
    currency: Currency
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("symbol")
    @classmethod
    def _clean_symbol(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if not cleaned:
            raise ValueError("symbol cannot be blank")
        return cleaned


class AssetUpdate(CashMoveRequest):
    symbol: str | None = Field(default=None, min_length=1, max_length=32)
    kind: MarketKind | None = None
    # `min_length=1` on a nullable field means "may be omitted, may not be
    # blank": clearing the name is refused here, in words, instead of by a
    # NOT NULL constraint surfacing as a 500.
    name: str | None = Field(default=None, min_length=1, max_length=200)
    quantity: float | None = Field(default=None, ge=0)
    cost_basis: float | None = Field(default=None, ge=0)
    currency: Currency | None = None
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("symbol")
    @classmethod
    def _clean_symbol(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().upper()
        if not cleaned:
            raise ValueError("symbol cannot be blank")
        return cleaned


class AssetOut(BaseModel):
    """A position as stored, plus its valuation — or None where it is unknown.

    Nothing here is defaulted to zero. A zero is a fact ("you own none"), and
    using it for "we do not know" is how a tracker starts lying.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    name: str
    kind: MarketKind
    quantity: float
    currency: Currency
    cost_basis: float | None
    note: str | None

    price: float | None = None
    price_currency: str | None = None
    price_as_of: str | None = None
    price_fetched_at: str | None = None

    value: float | None = None
    value_base: float | None = None
    cost_base: float | None = None
    gain: float | None = None
    gain_pct: float | None = None
    reason: str | None = None

    #: What the cash side of this trade did. None when the endpoint never
    #: touches cash (a price refresh, a read).
    cash: CashMoveOut | None = None


class AssetSellRequest(CashMoveRequest):
    """Sell some or all of a position, at a price the user states.

    Only two things are asked for, because only two things are facts the app
    cannot look up: how much was sold and how much money came back. The gain is
    derived from those plus the position's own cost basis — never from the
    current market price, which is what the position would be worth if it had
    not been sold.

    The currency of `proceeds` is not a field: money received for a position is
    in the market's currency for that symbol (the quote's), and falls back to
    the position's own only when nothing was ever quoted. Asking the user to
    choose would invite a USD figure to be recorded as dong.
    """

    quantity: float = Field(gt=0)
    #: Total received, not a price per unit — the same rule as `cost_basis`,
    #: and for the same reason: a per-unit price cannot be added up across
    #: several sales without knowing each one's size.
    proceeds: float = Field(ge=0)
    #: Defaults to today, server-side.
    sold_on: date | None = None
    note: str | None = Field(default=None, max_length=1000)


class RealizedOut(BaseModel):
    """One closed position, with what it sold for against what it released.

    Every base-currency figure is None-able, and for two different reasons that
    the `reason` field tells apart: money that could not be converted, and a
    cost nobody recorded.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    name: str
    kind: MarketKind
    quantity: float
    #: The currency the cost was recorded in.
    currency: Currency
    sold_on: str
    note: str | None

    proceeds: float
    #: The market's currency; not `Currency`, because a quote may arrive in a
    #: currency this app records but deliberately cannot convert.
    proceeds_currency: str
    cost_removed: float | None

    proceeds_base: float | None = None
    cost_base: float | None = None
    gain: float | None = None
    gain_pct: float | None = None
    reason: str | None = None

    #: What the cash side of this trade did. None when the endpoint never
    #: touches cash (a price refresh, a read).
    cash: CashMoveOut | None = None


class CashOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    currency: Currency
    balance: float
    balance_at: str
    note: str | None

    value_base: float | None = None
    reason: str | None = None

    #: The movement a balance edit recorded, when there was one. Reading a
    #: balance never has one; changing it always does, because a balance that
    #: moved with no line under it is what the history exists to prevent.
    cash: CashMoveOut | None = None


class CashEntryRequest(BaseModel):
    """Money the user says went into or came out of a balance.

    Not a trade, and not categorised: a salary, a bill, a gift, a transfer from
    a bank the app does not track. The reason is free text, because the moment a
    reason becomes a category this app has become the budgeting tool it
    deliberately is not (docs/SPEC.md §1.2).
    """

    #: Positive, in the pot's own currency. Which way it went is `direction`,
    #: not a sign: a form asking for "-500000" to mean a withdrawal is a form
    #: that will one day record one the wrong way round.
    amount: float = Field(gt=0)
    direction: Literal["in", "out"]
    #: Defaults to today, server-side.
    occurred_on: date | None = None
    note: str | None = Field(default=None, max_length=1000)


class CashEntryOut(BaseModel):
    """The balance after an entry, and the line that explains it."""

    account: "CashOut"
    cash: CashMoveOut


class CashUpdate(BaseModel):
    """An edit to one pot: its label, its balance, its note.

    The currency is absent on purpose. It is the pot's identity — one pot per
    currency, enforced by the database and by `app.cash` — so "change this pot's
    currency" is not an edit, it is a different pot.
    """

    name: str | None = Field(default=None, min_length=1, max_length=120)
    balance: float | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=1000)


# --------------------------------------------------------------------------
# Portfolio
# --------------------------------------------------------------------------


class KindTotal(BaseModel):
    kind: str
    value: float
    count: int


class CurrencyTotal(BaseModel):
    """Exposure to one currency.

    `amount` is in that currency and is NOT comparable with another row's;
    `value_base` is the same money in the base and is what may be summed or
    compared. The pair is returned together so the UI can never show one and
    label it the other.
    """

    currency: str
    amount: float
    value_base: float
    decimals: int = 2


class RateUsed(BaseModel):
    currency: str
    rate: float
    as_of: str
    source: str
    stale: bool


class Unconverted(BaseModel):
    kind: str
    id: int
    label: str
    reason: str | None = None


class CashMovementOut(BaseModel):
    """One movement of a cash balance, and what caused it.

    A signed amount in the account's currency, with the holding it belongs to
    snapshotted rather than pointed at: after a position is deleted, the row is
    the only thing that can still say where the money went.
    """

    id: int
    account_id: int
    subject: SubjectKindLiteral
    action: FlowActionLiteral
    #: The holding's id at the time, null once it is gone.
    holding_id: int | None
    symbol: str | None
    name: str
    #: Signed: negative is money out of the account.
    amount: float
    currency: str
    #: Units of `currency` per 1 of the holding's, when the two differed.
    rate: float | None
    occurred_on: str
    note: str | None


class PortfolioCounts(BaseModel):
    assets: int
    cash: int
    deposits: int
    gold: int
    unconverted: int


class PortfolioOut(BaseModel):
    base_currency: Currency
    total: float
    market_value: float
    cash_value: float
    #: Principal plus accrued interest across every term deposit.
    deposit_value: float
    #: Every gold holding valued at the shop's price for its product line.
    gold_value: float
    cost_base: float | None
    gain: float | None
    gain_pct: float | None
    #: Closed positions, newest first, and the figures the dashboard shows
    #: beside the unrealised ones. `realized_gain` is None when any sale is
    #: missing a cost; `total_gain` is None when either side is unknown.
    realized: list[RealizedOut]
    realized_gain: float | None
    realized_cost_base: float | None
    realized_count: int
    total_gain: float | None
    total_gain_pct: float | None
    #: Every cash movement, newest first. One list rather than a page per
    #: account: the Cash page shows each account's own history by filtering it,
    #: and the Dashboard can count what moved without a second request.
    movements: list[CashMovementOut]
    assets: list[AssetOut]
    cash: list[CashOut]
    deposits: list[DepositOut]
    gold: list[GoldOut]
    by_kind: list[KindTotal]
    by_currency: list[CurrencyTotal]
    unconverted: list[Unconverted]
    rates: list[RateUsed]
    counts: PortfolioCounts


class ValuationPoint(BaseModel):
    as_of: str
    base_currency: str
    total: float
    market_value: float
    cash_value: float
    deposit_value: float = 0.0
    gold_value: float = 0.0
    cost_value: float | None
    unconverted_count: int


class HistoryOut(BaseModel):
    base_currency: Currency
    points: list[ValuationPoint]


# --------------------------------------------------------------------------
# Market
# --------------------------------------------------------------------------


class SuggestionOut(BaseModel):
    symbol: str
    name: str
    kind: str | None = None
    exchange: str | None = None
    currency: str | None = None
    score: float = 0.0


class SearchOut(BaseModel):
    query: str
    suggestions: list[SuggestionOut]
    #: True when the feed could not be reached — the user can still type.
    degraded: bool = False


class PriceRow(BaseModel):
    symbol: str
    price: float
    currency: str | None
    as_of: str
    fetched_at: str
    error: str | None = None
    #: Where the number came from: "market" for a listed close, "fund" for a
    #: NAV published by a fund's management company. A NAV and a close are not
    #: the same kind of fact and the interface says which it is showing.
    source: str = "market"


class FxRow(BaseModel):
    base: str
    currency: str
    as_of: str
    rate: float
    source: str
    fetched_at: str


class MarketOut(BaseModel):
    base_currency: Currency
    prices: list[PriceRow]
    rates: list[FxRow]


class RefreshFailure(BaseModel):
    symbol: str
    error: str


class PriceRefreshOut(BaseModel):
    ok: bool
    refreshed: list[str]
    failed: list[RefreshFailure]
    asked: int


class FxBaseReport(BaseModel):
    """What one base's refresh did."""

    ok: bool
    error: str | None = None
    stored: list[str]
    as_of: str


class FxRefreshOut(BaseModel):
    """The result of refreshing rates.

    `bases` says what happened per base currency, because a refresh covers
    every base the user can switch to, and one of them failing while the other
    succeeds is a thing the UI has to be able to say.
    """

    ok: bool
    error: str | None = None
    stored: list[str]
    as_of: str
    bases: dict[str, FxBaseReport] = {}


class RefreshAllOut(BaseModel):
    prices: PriceRefreshOut
    fx: FxRefreshOut


class HealthOut(BaseModel):
    status: str
    version: str


# --------------------------------------------------------------------------
# Term deposits (savings)
# --------------------------------------------------------------------------


class DepositCreate(CashMoveRequest):
    name: str = Field(min_length=1, max_length=120)
    currency: Currency
    principal: float = Field(gt=0)
    #: Percent per year, as the contract quotes it: 6.5 means 6.5%.
    annual_rate: float = Field(ge=0, le=100)
    start_date: date
    #: Null is a demand deposit (không kỳ hạn): no end, keeps accruing.
    maturity_date: date | None = None
    interest_mode: Literal["at_maturity"] = "at_maturity"
    note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _maturity_is_after_the_start(self) -> "DepositCreate":
        if self.maturity_date is not None and self.maturity_date < self.start_date:
            raise ValueError("maturity_date cannot be before start_date")
        return self


class DepositUpdate(CashMoveRequest):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    currency: Currency | None = None
    principal: float | None = Field(default=None, gt=0)
    annual_rate: float | None = Field(default=None, ge=0, le=100)
    start_date: date | None = None
    maturity_date: date | None = None
    interest_mode: Literal["at_maturity"] | None = None
    note: str | None = Field(default=None, max_length=1000)


class DepositOut(BaseModel):
    """A deposit as computed for today, plus the same figures in the base.

    `value_base` is null when the deposit's currency cannot be converted, and
    `reason` says so; the deposit is then excluded from the portfolio total
    rather than counted at face value in the wrong unit.
    """

    id: int
    name: str
    currency: Currency
    principal: float
    annual_rate: float
    start_date: str
    maturity_date: str | None
    interest_mode: str
    note: str | None

    as_of: str
    days_accrued: int
    interest_accrued: float
    value: float
    matured: bool
    days_remaining: int | None
    value_at_maturity: float

    value_base: float | None = None
    interest_base: float | None = None
    reason: str | None = None

    #: What the cash side of this trade did. None when the endpoint never
    #: touches cash (a price refresh, a read).
    cash: CashMoveOut | None = None


class GoldOut(BaseModel):
    """A gold holding as valued today.

    `shop_price` and `price` are both present because they are different
    numbers: the first is the shop's figure for its own product line, the
    second is that figure expressed for ONE unit of the unit held. Showing only
    the first would invite multiplying it by a weight in the wrong unit, which
    is a factor of ten in gold.

    `from_attributes` because the valuation layer hands over a dataclass rather
    than a dict: the arithmetic and the response shape are deliberately not the
    same object.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    currency: Currency
    quantity: float
    unit: str
    pricing: str
    note: str | None

    product_key: str
    product_name: str | None
    shop_price: float | None
    price: float | None
    price_as_of: str | None
    price_source: str | None

    value: float | None
    value_base: float | None
    cost_basis: float | None
    reason: str | None = None

    #: What the cash side of this trade did. None when the endpoint never
    #: touches cash (a price refresh, a read).
    cash: CashMoveOut | None = None


class GoldCreate(CashMoveRequest):
    name: str = Field(min_length=1, max_length=120)
    currency: Currency
    quantity: float = Field(gt=0)
    unit: Literal["ounce", "chi", "luong", "gram"] = "chi"
    #: The goldshop product line to follow, as `app.gold.normalise_key` makes
    #: it. Refused if the shop does not currently publish it, so a holding can
    #: never start life pointing at nothing.
    product_key: str = Field(min_length=1, max_length=200)
    #: The default is the shop's asking price, which is what a "gold price"
    #: means and what every other holding here is valued at.
    pricing: Literal["sell", "buy"] = "sell"
    cost_basis: float | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=1000)


class GoldUpdate(CashMoveRequest):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    currency: Currency | None = None
    quantity: float | None = Field(default=None, gt=0)
    unit: Literal["ounce", "chi", "luong", "gram"] | None = None
    product_key: str | None = Field(default=None, min_length=1, max_length=200)
    pricing: Literal["buy", "sell"] | None = None
    cost_basis: float | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=1000)


class GoldProductOut(BaseModel):
    """One line a goldshop publishes, normalised to a price per chỉ."""

    key: str
    name: str
    buy: float
    sell: float
    unit: str
    updated_at: str
    #: The date part of `updated_at`, as this app stores dates.
    updated_on: str


class GoldProductList(BaseModel):
    products: list[GoldProductOut]
    #: True when the shop could not be reached — the picker says so rather than
    #: showing an empty list as though nothing existed.
    degraded: bool = False
    error: str | None = None
    #: Where the prices come from, said in the response so the interface never
    #: has to hard-code the name of a shop.
    source: str


class DepositRollRequest(BaseModel):
    """Roll a matured deposit into a new term.

    Everything is optional: with nothing given, the same term repeats — same
    bank, same rate, a new period of the same length — and the interest earned
    becomes part of the new principal, which is what "tất toán và gửi lại" does
    at a counter.
    """

    #: New principal. Defaults to the current value (principal + interest).
    principal: float | None = Field(default=None, gt=0)
    annual_rate: float | None = Field(default=None, ge=0, le=100)
    #: New start date. Defaults to the day the old term matured.
    start_date: date | None = None
    #: New maturity. Defaults to the same number of days as the term just ended.
    maturity_date: date | None = None
    note: str | None = Field(default=None, max_length=1000)


class DepositWithdrawRequest(CashMoveRequest):
    """Matured money comes out: the deposit is closed and the money lands in cash.

    Both halves happen in one request on purpose. Doing it in two screens is
    how a portfolio ends up holding the same million twice — once as a deposit
    that was never closed and once as cash that arrived.

    Where it lands is not a choice: the pot of the deposit's own currency, which
    is the only cash there is (see `app.cash`). A term deposit is not a new pile
    of money — it is the same money coming back.

    `balance` is what the bank actually paid, when that differs from what the
    arithmetic says. Nothing else is asked: the destination is the pot.
    """

    balance: float | None = Field(default=None, ge=0)


class DepositWithdrawOut(BaseModel):
    """A closed deposit, the account the money landed in, and what moved.

    `account` rather than `cash`, because `cash` on every other response means
    "what the cash side did" (`CashMoveOut`) and two different shapes under one
    name is how a client reads the wrong one.
    """

    closed_deposit_id: int
    account: "CashOut"
    amount: float
    cash: CashMoveOut
