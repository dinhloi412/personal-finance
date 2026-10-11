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

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app import money

# The three aliases below are the same three closed sets as `app.money`'s, and
# they are cross-checked against it at import time: a `Literal` cannot be built
# from a variable in Python, so the only way to keep one definition is to make
# a disagreement impossible to miss. `tests/test_scope.py` asserts on the result.
assert money.CURRENCIES == ("VND", "USD")
assert money.LANGUAGES == ("vi", "en")
assert money.MARKET_KINDS == ("stock", "fund", "crypto")

Currency = Literal["VND", "USD"]
MarketKind = Literal["stock", "fund", "crypto"]
LanguageLiteral = Literal["vi", "en"]


# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------


class SettingsOut(BaseModel):
    base_currency: Currency
    language: LanguageLiteral
    supported_currencies: list[str]
    supported_kinds: list[str]
    supported_languages: list[str]
    #: Where the SQLite file lives, shown in Settings so the user can back it up.
    database_path: str
    version: str


class SettingsPatch(BaseModel):
    base_currency: Currency | None = None
    language: LanguageLiteral | None = None


class WipeOut(BaseModel):
    """What a wipe removed, per table, so the confirmation can say it plainly."""

    removed: dict[str, int]


# --------------------------------------------------------------------------
# Assets (market positions)
# --------------------------------------------------------------------------


class AssetCreate(BaseModel):
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


class AssetUpdate(BaseModel):
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


class CashCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    currency: Currency
    balance: float
    note: str | None = Field(default=None, max_length=1000)


class CashUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    currency: Currency | None = None
    balance: float | None = None
    note: str | None = Field(default=None, max_length=1000)


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


class PortfolioCounts(BaseModel):
    assets: int
    cash: int
    unconverted: int


class PortfolioOut(BaseModel):
    base_currency: Currency
    total: float
    market_value: float
    cash_value: float
    cost_base: float | None
    gain: float | None
    gain_pct: float | None
    assets: list[AssetOut]
    cash: list[CashOut]
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
