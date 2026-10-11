"""Market data: what a symbol is called, and what it last closed at.

Source is Yahoo Finance through `yfinance`. Two decisions are worth knowing
about:

**A close, not a "live price".** Yahoo's realtime quote endpoint answers `None`
from plenty of networks, and answers with a number that is not reproducible when
it does. So `quote()` reads a short history window and takes the last CLOSE it
finds, with the session date attached. It is delayed by up to a day; for
tracking what you hold, that is the right trade.

**Search suggests, it does not decide.** `search()` is for filling in a form.
Nothing in this app *requires* a search to succeed: every field it fills is
also typeable by hand, so a renamed listing or a search outage costs the user a
click, not their portfolio.

Every network call lives in a `_fetch_*` helper so tests monkeypatch that one
name and never touch the wire.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, timedelta

from app.money import MarketKind

logger = logging.getLogger(__name__)

#: How far back to look for a session that has a close in it. Long enough to
#: cross a holiday week, short enough that the answer is still "now".
RECENT_DAYS = 10

#: Yahoo `quoteType` → our kind. Anything absent is not something this app
#: tracks: an index cannot be held, a future expires, a currency is cash.
QUOTE_TYPE_TO_KIND: dict[str, MarketKind] = {
    "EQUITY": "stock",
    "ETF": "fund",
    "MUTUALFUND": "fund",
    "CRYPTOCURRENCY": "crypto",
}

#: Exchange suffix → listing currency, only for suffixes where the currency is
#: not in doubt. Vietnam and the US are the two this app holds, and both are
#: unambiguous. Never treat an absent entry as VND.
SUFFIX_TO_CURRENCY: dict[str, str] = {
    ".VN": "VND",
    ".HM": "VND",
    ".HN": "VND",
    ".UP": "VND",
}

#: Crypto pairs Yahoo quotes in these; a bare `BTC` is completed to `BTC-USD`.
_CRYPTO_QUOTES = ("-USD", "-EUR", "-VND", "-USDT", "-USDC")


class MarketError(Exception):
    """The market could not be reached, or answered with nothing usable."""


@dataclass(frozen=True)
class Quote:
    """What one symbol last closed at, and the day that close belongs to."""

    symbol: str
    price: float
    currency: str | None
    as_of: str  # the market close date, YYYY-MM-DD
    name: str | None = None


@dataclass(frozen=True)
class Suggestion:
    """One search hit. Every field is displayable and none is required."""

    symbol: str
    name: str
    kind: str | None = None
    exchange: str | None = None
    currency: str | None = None
    score: float = 0.0


# --------------------------------------------------------------------------
# Network helpers — the only functions in this module that talk to Yahoo.
# --------------------------------------------------------------------------


def _fetch_search(query: str, limit: int) -> list[dict]:
    """Raw Yahoo search results. Isolated so tests can replace it."""
    import yfinance as yf

    results = yf.Search(query, max_results=limit)
    return list(getattr(results, "quotes", None) or [])


def _fetch_history(symbol: str, period: str = f"{RECENT_DAYS}d"):
    """Raw close history for a symbol, as a DataFrame. Isolated for tests."""
    import yfinance as yf

    return yf.Ticker(symbol).history(period=period, auto_adjust=False)


def _fetch_currency(symbol: str) -> str | None:
    """The listing currency Yahoo reports for a symbol, or None."""
    import yfinance as yf

    ticker = yf.Ticker(symbol)
    for attribute in ("fast_info", "info"):
        try:
            source = getattr(ticker, attribute)
            code = source.get("currency") if hasattr(source, "get") else None
        except Exception:  # noqa: BLE001 — a missing field is not an error
            continue
        if code:
            return str(code).upper()
    return None


# --------------------------------------------------------------------------
# Pure helpers
# --------------------------------------------------------------------------


def kind_from_quote_type(quote_type: str | None) -> MarketKind | None:
    """Map Yahoo's `quoteType` to ours; None if this app does not track it."""
    if not quote_type:
        return None
    return QUOTE_TYPE_TO_KIND.get(quote_type.upper())


def currency_from_symbol(symbol: str) -> str | None:
    """The currency a symbol's suffix implies, or None if it implies nothing.

    A guess used only to fill a form and to seed a first quote. A wrong guess
    here costs a dropdown correction; the quote's own currency always wins.
    """
    upper = symbol.upper()
    if any(upper.endswith(suffix) for suffix in _CRYPTO_QUOTES):
        return "USD"
    for suffix, currency in SUFFIX_TO_CURRENCY.items():
        if upper.endswith(suffix):
            return currency
    # A bare ticker with no suffix is a US listing; `BTC` is completed instead.
    if re.fullmatch(r"[A-Z]{1,6}", upper):
        return "USD"
    return None


def normalise_symbol(symbol: str, kind: str | None = None) -> str:
    """Trim, upper-case, and complete a bare crypto ticker to a quoted pair."""
    cleaned = symbol.strip().upper()
    if kind == "crypto" and not any(cleaned.endswith(q) for q in _CRYPTO_QUOTES):
        return f"{cleaned}-USD"
    return cleaned


# --------------------------------------------------------------------------
# Public reads
# --------------------------------------------------------------------------


def quote(symbol: str, *, name: str | None = None) -> Quote:
    """The most recent close for `symbol`, with its session date.

    Raises `MarketError` when the symbol cannot be priced at all. A symbol that
    simply has no session yet (a weekend, a newly listed instrument) is a
    `MarketError` too, worded so the user can tell what happened.
    """
    cleaned = normalise_symbol(symbol)
    if not cleaned:
        raise MarketError("no symbol given")

    try:
        history = _fetch_history(cleaned)
    except Exception as cause:  # noqa: BLE001 — every yfinance failure is ours
        raise MarketError(f"market unreachable for {cleaned}: {cause}") from cause

    if history is None or len(history) == 0:
        raise MarketError(f"no quote for {cleaned}")

    closes = history["Close"].dropna()
    if len(closes) == 0:
        raise MarketError(f"no close for {cleaned}")

    price = float(closes.iloc[-1])
    as_of = _as_of(history.index[-1])

    currency = currency_from_symbol(cleaned)
    try:
        reported = _fetch_currency(cleaned)
    except Exception:  # noqa: BLE001 — the suffix guess already covers us
        reported = None
    if reported:
        currency = reported

    return Quote(symbol=cleaned, price=price, currency=currency, as_of=as_of, name=name)


def _as_of(index_label) -> str:
    """The date of a history row, however pandas hands it over."""
    stamp = getattr(index_label, "date", None)
    if callable(stamp):
        return stamp().isoformat()
    if isinstance(index_label, date):
        return index_label.isoformat()
    return str(index_label)[:10]


def search(query: str, *, limit: int = 12) -> list[Suggestion]:
    """Symbols and names matching `query`, best first.

    Only kinds this app tracks are returned: a hit that cannot be held is
    noise in a picker whose whole job is choosing something to hold.
    """
    text = query.strip()
    if not text:
        return []

    try:
        rows = _fetch_search(text, limit * 2)
    except Exception as cause:  # noqa: BLE001
        logger.warning("search failed for %r: %s", text, cause)
        raise MarketError(f"search unavailable: {cause}") from cause

    suggestions: list[Suggestion] = []
    seen: set[str] = set()
    for row in rows:
        symbol = str(row.get("symbol") or "").strip()
        if not symbol or symbol in seen:
            continue
        quote_type = row.get("quoteType") or row.get("typeDisp")
        kind = kind_from_quote_type(quote_type)
        if kind is None:
            continue
        seen.add(symbol)
        suggestions.append(
            Suggestion(
                symbol=symbol,
                name=str(row.get("longname") or row.get("shortname") or symbol),
                kind=kind,
                exchange=row.get("exchDisp") or row.get("exchange"),
                currency=currency_from_symbol(symbol),
                score=float(row.get("score") or 0.0),
            )
        )
        if len(suggestions) >= limit:
            break

    return suggestions


def lookup_symbol(symbol: str, *, kind: str | None = None) -> Suggestion | None:
    """Resolve one symbol on its own, when search found nothing.

    `BTC-USD` and `VIC.VN` are perfectly good symbols that a text search does
    not always return. This asks the quote endpoint directly, so the picker can
    still fill in a name and a currency the user typed.
    """
    cleaned = normalise_symbol(symbol, kind)
    try:
        priced = quote(cleaned)
    except MarketError:
        return None
    return Suggestion(
        symbol=priced.symbol,
        name=priced.name or cleaned,
        kind=kind or kind_for_quote_symbol(priced.symbol),
        exchange=None,
        currency=priced.currency,
    )


def kind_for_quote_symbol(symbol: str) -> str | None:
    """Best-effort kind for a symbol known only by its quote."""
    if any(symbol.upper().endswith(q) for q in _CRYPTO_QUOTES):
        return "crypto"
    return None


def days_ago(days: int) -> str:
    """A date `days` before today, as YYYY-MM-DD. Used by the staleness rule."""
    return (date.today() - timedelta(days=days)).isoformat()
