"""The vocabulary the whole app shares: what can be held, in what, and how it
is spoken about.

Three closed sets, defined once and imported everywhere, because each of them
is enforced in four places (schema, ORM, valuation, UI) and four copies of a
list is four chances for the fifth entry to reach only three of them.

- `CURRENCIES`: what a balance or a price may be denominated in.
- `MARKET_KINDS`: what is priced by a feed, as opposed to counted by hand.
- `LANGUAGES`: what the interface may be read in.

`ASSET_KINDS` is `MARKET_KINDS` plus cash, and cash is deliberately *not* in
`MARKET_KINDS`: cash has no symbol, no price and no cost basis, so anything
that loops over market kinds must not be handed it.
"""

from __future__ import annotations

from typing import Final, Literal, get_args

Currency = Literal["VND", "USD"]
BaseCurrency = Literal["VND", "USD"]
MarketKind = Literal["stock", "fund", "crypto"]
AssetKind = Literal["stock", "fund", "crypto", "cash"]
Language = Literal["vi", "en"]

CURRENCIES: Final[tuple[Currency, ...]] = get_args(Currency)
BASE_CURRENCIES: Final[tuple[BaseCurrency, ...]] = get_args(BaseCurrency)
MARKET_KINDS: Final[tuple[MarketKind, ...]] = get_args(MarketKind)
ASSET_KINDS: Final[tuple[AssetKind, ...]] = get_args(AssetKind)
LANGUAGES: Final[tuple[Language, ...]] = get_args(Language)

DEFAULT_BASE_CURRENCY: Final[BaseCurrency] = "VND"
DEFAULT_LANGUAGE: Final[Language] = "vi"

#: Symbols whose quote is useful only as a canary, never as a holding.
CRYPTO_QUOTE_SUFFIXES: Final[tuple[str, ...]] = ("-USD", "-EUR", "-VND", "-USDT")

#: Decimals used when showing each currency. VND has no minor unit in practice;
#: showing "25.000,00 ₫" invents precision the money does not have.
DECIMALS: Final[dict[str, int]] = {"VND": 0, "USD": 2}


def decimals_for(currency: str) -> int:
    """How many decimal places to show an amount in `currency`."""
    return DECIMALS.get(currency.upper(), 2)


def is_supported_currency(code: str | None) -> bool:
    """True if `code` is a currency this app can hold and add up."""
    return bool(code) and code.upper() in CURRENCIES
