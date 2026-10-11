"""The vocabulary the whole app shares: what can be held, in what, and how it
is spoken about.

Four closed sets, defined once and imported everywhere, because each of them
is enforced in four places (schema, ORM, valuation, UI) and four copies of a
list is four chances for the fifth entry to reach only three of them.

- `CURRENCIES`: what a balance or a price may be denominated in.
- `MARKET_KINDS`: what is priced by a feed, as opposed to computed or counted.
- `ASSET_KINDS`: everything that makes up the net worth, including the two
  things that have no feed behind them — cash, which the user counts, and a
  term deposit, whose value is computed from its own terms.
- `LANGUAGES`: what the interface may be read in.

`MARKET_KINDS` deliberately excludes cash and deposits: neither has a symbol,
a quote or a cost basis, so anything that loops over market kinds must not be
handed one.
"""

from __future__ import annotations

from typing import Final, Literal, get_args

Currency = Literal["VND", "USD"]
BaseCurrency = Literal["VND", "USD"]
MarketKind = Literal["stock", "fund", "crypto"]
AssetKind = Literal["stock", "fund", "crypto", "cash", "deposit"]
Language = Literal["vi", "en"]

#: How a term deposit pays its interest. Only one behaviour is implemented,
#: and the type says so rather than offering a choice that does nothing.
InterestMode = Literal["at_maturity"]

CURRENCIES: Final[tuple[Currency, ...]] = get_args(Currency)
BASE_CURRENCIES: Final[tuple[BaseCurrency, ...]] = get_args(BaseCurrency)
MARKET_KINDS: Final[tuple[MarketKind, ...]] = get_args(MarketKind)
ASSET_KINDS: Final[tuple[AssetKind, ...]] = get_args(AssetKind)
LANGUAGES: Final[tuple[Language, ...]] = get_args(Language)
INTEREST_MODES: Final[tuple[InterestMode, ...]] = get_args(InterestMode)

DEFAULT_BASE_CURRENCY: Final[BaseCurrency] = "VND"
DEFAULT_LANGUAGE: Final[Language] = "vi"
DEFAULT_INTEREST_MODE: Final[InterestMode] = "at_maturity"

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
