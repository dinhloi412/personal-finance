"""The vocabulary the whole app shares: what can be held, in what, and how it
is spoken about.

Six closed sets, defined once and imported everywhere, because each of them
is enforced in four places (schema, ORM, valuation, UI) and four copies of a
list is four chances for the fifth entry to reach only three of them.

- `CURRENCIES`: what a balance or a price may be denominated in.
- `MARKET_KINDS`: what is priced by a feed, as opposed to computed or counted.
- `ASSET_KINDS`: everything that makes up the net worth, including the two
  things that have no feed behind them — cash, which the user counts, and a
  term deposit, whose value is computed from its own terms.
- `LANGUAGES`: what the interface may be read in.
- `SUBJECT_KINDS`: what a cash movement can be caused by — a trade in one of
  the three kinds of holding, or the cash page itself when money comes in or
  goes out for a reason that is not an investment (a salary, a bill).
- `FLOW_ACTIONS`: what that movement was.

`MARKET_KINDS` deliberately excludes cash and deposits: neither has a symbol,
a quote or a cost basis, so anything that loops over market kinds must not be
handed one.
"""

from __future__ import annotations

from typing import Final, Literal, get_args

Currency = Literal["VND", "USD"]
BaseCurrency = Literal["VND", "USD"]
MarketKind = Literal["stock", "fund", "crypto"]
AssetKind = Literal["stock", "fund", "crypto", "cash", "deposit", "gold"]
#: What can move money in or out of a cash balance. `cash` is the odd one: not
#: a holding, but the user putting money in or taking it out themselves, which
#: the app records so that a balance always has a history behind it.
SubjectKind = Literal["asset", "gold", "deposit", "cash"]
#: Why a cash movement happened. Kept structured rather than as a written
#: sentence, because the sentence has to exist in two languages.
#:
#: - `buy` / `sell`: a market position bought or sold.
#: - `open` / `close`: a term deposit opened, or paid out at maturity.
#: - `adjust`: a corrected figure, where only the difference moved — an edited
#:   cost basis or principal, or a balance the user counted and found different.
#: - `refund`: a holding deleted. The money that had actually left the account
#:   for it comes back; see `app.movements.net_invested`.
#: - `in` / `out`: money the user says entered or left a cash balance, with no
#:   holding behind it. There is no category here on purpose: a reason is free
#:   text, not a budget line (see docs/SPEC.md §1.2).
FlowAction = Literal[
    "buy", "sell", "open", "close", "adjust", "refund", "in", "out"
]
#: The weights gold is actually bought and sold in. An ounce is the world
#: market's unit; a chỉ and a lượng are Vietnam's, and a lượng is ten chỉ by
#: definition — which is why the two are defined from one number below.
#: The weights gold is held in. `chi` and `luong` are Vietnam's — a lượng is
#: ten chỉ by definition — and they are what a Vietnamese holding is kept in.
#: `gram` and `ounce` are here for completeness of the gram table below; the
#: shop this app reads quotes per chỉ.
GoldUnit = Literal["chi", "luong", "gram", "ounce"]

#: Which of a goldshop's two prices a holding is valued at.
#:
#: The default is **sell** — what the shop charges — because that is what "the
#: gold price" means to anyone reading one: the news says SJC is 144,8 triệu a
#: lượng, and that is the shop's asking price, not what it pays. It is also the
#: same basis as every other holding in this app: a stock, a fund and a crypto
#: are all valued at the price you would have to pay for them.
#:
#: **buy** is what the shop would pay you today. It is the honest figure for
#: "what could I get for this", and the difference between the two is the
#: spread — real money, which is why both are shown.
GoldPricing = Literal["sell", "buy"]
Language = Literal["vi", "en"]

#: How a term deposit pays its interest. Only one behaviour is implemented,
#: and the type says so rather than offering a choice that does nothing.
InterestMode = Literal["at_maturity"]

CURRENCIES: Final[tuple[Currency, ...]] = get_args(Currency)
BASE_CURRENCIES: Final[tuple[BaseCurrency, ...]] = get_args(BaseCurrency)
MARKET_KINDS: Final[tuple[MarketKind, ...]] = get_args(MarketKind)
ASSET_KINDS: Final[tuple[AssetKind, ...]] = get_args(AssetKind)
SUBJECT_KINDS: Final[tuple[SubjectKind, ...]] = get_args(SubjectKind)
FLOW_ACTIONS: Final[tuple[FlowAction, ...]] = get_args(FlowAction)
GOLD_UNITS: Final[tuple[GoldUnit, ...]] = get_args(GoldUnit)
GOLD_PRICINGS: Final[tuple[GoldPricing, ...]] = get_args(GoldPricing)
LANGUAGES: Final[tuple[Language, ...]] = get_args(Language)
INTEREST_MODES: Final[tuple[InterestMode, ...]] = get_args(InterestMode)

DEFAULT_BASE_CURRENCY: Final[BaseCurrency] = "VND"
DEFAULT_LANGUAGE: Final[Language] = "vi"
DEFAULT_INTEREST_MODE: Final[InterestMode] = "at_maturity"
DEFAULT_GOLD_UNIT: Final[GoldUnit] = "chi"
DEFAULT_GOLD_PRICING: Final[GoldPricing] = "sell"
#: Named separately because the model's default reads better as a constant than
#: as a bare string, which is a word that means several things.
GOLD_PRICING_SELL: Final[GoldPricing] = "sell"

#: A troy ounce, in grams. Not a unit this app prices in — the gold it tracks is
#: Vietnamese and quoted per chỉ — but kept in the gram table so a weight given
#: in ounces converts rather than being refused.
TROY_OUNCE_IN_GRAMS: Final[float] = 31.1034768

#: A Vietnamese chỉ (also called a "đồng cân"), in grams. 3.75 g exactly, which
#: makes a lượng 37.5 g. This is a definition, not a measurement.
CHI_IN_GRAMS: Final[float] = 3.75

#: Grams per unit, for every unit gold is held in. Defined from the two
#: constants above so the units can never disagree with each other: a lượng
#: that was not ten chỉ would be a bug in every conversion at once.
GRAMS_PER_UNIT: Final[dict[str, float]] = {
    "gram": 1.0,
    "chi": CHI_IN_GRAMS,
    "luong": CHI_IN_GRAMS * 10,
    "ounce": TROY_OUNCE_IN_GRAMS,
}

#: The unit gold is held in here. A single value rather than a per-currency
#: map: the shop this app reads is Vietnamese and quotes per chỉ, and a holding
#: kept in dollars is still that same gold — being wrong about the unit is a
#: factor of ten, so it is not a thing to infer from a currency.
PREFERRED_GOLD_UNIT: Final[GoldUnit] = "chi"

#: Symbols whose quote is useful only as a canary, never as a holding.
CRYPTO_QUOTE_SUFFIXES: Final[tuple[str, ...]] = ("-USD", "-EUR", "-VND", "-USDT")

#: Decimals used when showing each currency. VND has no minor unit in practice;
#: showing "25.000,00 ₫" invents precision the money does not have.
DECIMALS: Final[dict[str, int]] = {"VND": 0, "USD": 2}

#: Days in a year for interest arithmetic. Vietnamese term deposits quote a
#: year rate and pay on actual days held over a 365-day year, so this is the
#: divisor — not 360, which is the money-market convention and would overstate
#: every interest figure by about 1.4%.
DAYS_IN_YEAR: Final[int] = 365


def decimals_for(currency: str) -> int:
    """How many decimal places to show an amount in `currency`."""
    return DECIMALS.get(currency.upper(), 2)


def is_supported_currency(code: str | None) -> bool:
    """True if `code` is a currency this app can hold and add up."""
    return bool(code) and code.upper() in CURRENCIES
