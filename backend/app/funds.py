"""Open-ended Vietnamese funds, priced by NAV from Fmarket.

Yahoo has no open-ended fund: a fund certificate is not listed on an exchange,
so there is no ticker and no session close. What it has instead is a NAV — net
asset value per certificate — published once a day by the fund's management
company. This module is the second price source, for exactly that gap.

**The source is Fmarket** (<https://fmarket.vn>), a Vietnamese fund platform
with a plain JSON API that needs no key and answers with the current NAV and
the day it is for. Dragon Capital publishes the same numbers on its own site,
but as an HTML table, and a scraper for a page nobody promised to keep is a
maintenance cost this does not need to pay.

Three things about this source that shape the code:

**One fund, several names.** Fmarket lists Dragon Capital's funds under the
codes the fund company uses internally (`VFMVF4`) while the market, the fund's
own website and the certificate all say `DCDE`. Both are the same fund, and the
NAV is identical to the dong. `ALIASES` maps the name a person uses to the name
Fmarket answers to, so `DCDE` can be typed into the app and still be priced.
The mapping is short, explicit and checked by a test whose whole job is to
notice when a code stops resolving.

**NAV is daily, so one request a day is the whole budget.** A per-product lookup
is cached with the day it belongs to, and the app's own price cache already
refuses to ask twice in a day. There is no polling here and no retry storm: a
failed fetch leaves the last NAV in place, dated, exactly as a stale quote does.

**It cannot be asked for history.** The API answers "what is it worth now",
not "what was it worth on a day"; the endpoints for a NAV series are not public.
So a fund's value here is always current NAV, and a dated valuation of a fund
holdings is a thing this app cannot reconstruct from this source — which the
price cache's `as_of` makes visible rather than silent.
"""

from __future__ import annotations

import datetime
import json
import time
import urllib.request
from dataclasses import dataclass

from app.money import Currency

#: The two product families Fmarket publishes. Both are "funds this app can
#: hold": one is an open-ended fund you buy, the other a fund being issued.
PRODUCT_TYPES = ("NEW_FUND", "TRADING_FUND")

BASE_URL = "https://api.fmarket.vn/res"

#: Sent because a bare urllib request to a commercial API is rude; identifies
#: the caller so the operator can see what this is if they ever look.
USER_AGENT = "SoTaiSan/0.1 (personal asset tracker; one request per fund per day)"

TIMEOUT_SECONDS = 20

#: How long a fetched catalogue stays good. The catalogue is the list of funds
#: and their codes; it changes when a fund launches or is renamed, which is
#: rare, and a picker that re-fetched 69 rows on every keystroke would be an
#: unpleasant guest. The NAV inside these rows goes stale, which is why a
#: chosen fund is re-priced from its own endpoint rather than from the cache.
CATALOGUE_TTL_SECONDS = 6 * 60 * 60

_catalogue_cache: tuple[float, list["FundQuote"]] | None = None
_id_cache: tuple[float, dict[str, int]] | None = None

#: The fmarket code -> the code a person actually types.
#:
#: Only the names that genuinely differ. Fmarket uses the fund company's
#: internal scheme for Dragon Capital's funds, and the fund company's public
#: certificate uses another; every other manager publishes one code and both
#: sides use it, so those need no entry here.
#:
#: The NAVs were cross-checked against Dragon Capital's own published price
#: list on 2026-10-11 and matched to the dong (DCDE 24 582,29 ₫ = VFMVF4
#: 24 582,29 ₫), which is what makes this a mapping and not a guess.
ALIASES: dict[str, str] = {
    "DCDE": "VFMVF4",  # Quỹ đầu tư cổ phiếu tập trung cổ tức DC
    "DCDS": "VFMVF1",  # Quỹ đầu tư chứng khoán năng động DC
    "DCBF": "VFMVFB",  # Quỹ đầu tư trái phiếu DC
    "DCIP": "VFMVFC",  # Quỹ đầu tư trái phiếu gia tăng thu nhập cố định DC
}

#: A fund certificate is denominated in dong: Fmarket is a Vietnamese platform
#: and every product on it is quoted in VND. Named rather than assumed at each
#: use, so the day a second currency appears it appears in one place.
FUND_CURRENCY: Currency = "VND"


class FundError(Exception):
    """The fund could not be reached, or Fmarket does not carry it."""


@dataclass(frozen=True)
class FundQuote:
    """A fund's NAV, and the day the fund valued it.

    `symbol` is the code the user knows; `product_code` is Fmarket's name for
    the same fund. Both travel together so the interface can show the one the
    certificate says and the store can still ask for the right thing.
    """

    symbol: str
    product_code: str
    name: str
    nav: float
    currency: str
    as_of: str
    owner: str | None = None
    #: Fmarket's numeric id, needed to ask for the detail. Taken from the
    #: catalogue, which is the only place the API hands both out together.
    product_id: int = 0


def normalise(symbol: str) -> str:
    """Upper-case and trim, the way every other symbol in this app is stored."""
    return symbol.strip().upper()


def resolve_product_code(symbol: str) -> str:
    """The code Fmarket uses for `symbol`, which may be an alias of it."""
    cleaned = normalise(symbol)
    return ALIASES.get(cleaned, cleaned)


def is_alias(symbol: str) -> bool:
    """True when the code typed differs from the one Fmarket publishes."""
    cleaned = normalise(symbol)
    return cleaned in ALIASES


# --------------------------------------------------------------------------
# Network — the only functions here that touch Fmarket.
# --------------------------------------------------------------------------


def _post(path: str, payload: dict) -> dict:
    """POST JSON and return the parsed body. Isolated so tests replace it."""
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def _fetch_catalogue() -> list[dict]:
    """Every fund Fmarket carries, as raw rows. Isolated for tests."""
    body = _post(
        "/products/filter",
        {"types": list(PRODUCT_TYPES), "page": 1, "size": 200},
    )
    return list((body.get("data") or {}).get("rows") or [])


def _fetch_product(product_id: int) -> dict:
    """One product's detail, by its numeric id, which is what the API takes.

    Not by code: the path segment is bound to an integer, so `/products/VNDAF`
    answers 400 before any lookup happens. The id comes from the catalogue,
    which is one request and is remembered.
    """
    request = urllib.request.Request(
        f"{BASE_URL}/products/{product_id}",
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        body = json.loads(response.read().decode("utf-8"))
    return dict(body.get("data") or {})


def _catalogue_ids(*, fresh: bool = False) -> dict[str, int]:
    """Product code -> numeric id, from the catalogue.

    Its own small cache because it is only needed to turn a code into the id
    the detail endpoint wants, and the catalogue itself is cached for hours.
    """
    global _id_cache
    if not fresh and _id_cache is not None:
        fetched_at, cached = _id_cache
        if time.monotonic() - fetched_at < CATALOGUE_TTL_SECONDS:
            return cached

    ids: dict[str, int] = {}
    for fund in catalogue(fresh=fresh):
        ids[fund.product_code] = getattr(fund, "product_id", 0)
    _id_cache = (time.monotonic(), ids)
    return ids


# --------------------------------------------------------------------------
# Pure helpers
# --------------------------------------------------------------------------


def _date_from_epoch_ms(value: object) -> str | None:
    """Fmarket's millisecond timestamps as `YYYY-MM-DD`, or None."""
    if not isinstance(value, (int, float)) or value <= 0:
        return None
    try:
        return datetime.datetime.fromtimestamp(
            value / 1000, tz=datetime.timezone.utc
        ).date().isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def nav_date(product: dict) -> str | None:
    """The day the fund valued its NAV — not the day we asked for it.

    `extra.lastNAVDate` is the field that means this. `updateAt` is when the
    platform last touched the record and can be months older even though the
    NAV is from yesterday, so it is only a fallback.
    """
    extra = product.get("extra")
    if isinstance(extra, dict):
        found = _date_from_epoch_ms(extra.get("lastNAVDate"))
        if found:
            return found
    return _date_from_epoch_ms(product.get("updateAt"))


def nav_of(product: dict) -> float | None:
    """The NAV per certificate, preferring the explicit current value."""
    extra = product.get("extra")
    if isinstance(extra, dict):
        current = extra.get("currentNAV")
        if isinstance(current, (int, float)) and current > 0:
            return float(current)
    value = product.get("nav")
    if isinstance(value, (int, float)) and value > 0:
        return float(value)
    return None


def product_name(product: dict) -> str:
    """A readable name: the fund's own name, falling back to its short code."""
    return str(product.get("name") or product.get("shortName") or product.get("code") or "")


def owner_name(product: dict) -> str | None:
    owner = product.get("owner")
    if isinstance(owner, dict):
        return owner.get("shortName") or owner.get("name")
    return None


def _to_quote(product: dict, symbol: str) -> FundQuote:
    nav = nav_of(product)
    if nav is None:
        raise FundError(f"{symbol} has no NAV on Fmarket")
    product_code = str(product.get("code") or resolve_product_code(symbol))
    raw_id = product.get("id")
    return FundQuote(
        symbol=normalise(symbol),
        product_code=product_code,
        name=product_name(product),
        nav=nav,
        currency=FUND_CURRENCY,
        as_of=nav_date(product) or datetime.date.today().isoformat(),
        owner=owner_name(product),
        product_id=int(raw_id) if isinstance(raw_id, (int, float)) else 0,
    )


# --------------------------------------------------------------------------
# Public reads
# --------------------------------------------------------------------------


def quote(symbol: str) -> FundQuote:
    """The current NAV for one fund, under either of its names.

    Raises `FundError` when Fmarket does not carry it or does not answer. A
    symbol this app cannot price must fail loudly here so the caller can store
    the failure against the position, rather than quietly storing a zero.
    """
    cleaned = normalise(symbol)
    if not cleaned:
        raise FundError("no symbol given")

    product_code = resolve_product_code(cleaned)
    try:
        product_id = _catalogue_ids().get(product_code)
    except Exception as cause:  # noqa: BLE001
        raise FundError(f"Fmarket unreachable: {cause}") from cause

    if product_id is None:
        raise FundError(f"Fmarket does not carry {cleaned} ({product_code})")

    try:
        product = _fetch_product(product_id)
    except Exception as cause:  # noqa: BLE001 — every failure is "no NAV"
        raise FundError(f"Fmarket unreachable for {product_code}: {cause}") from cause

    if not product or not (product.get("code") or product.get("nav")):
        raise FundError(f"Fmarket returned nothing for {cleaned}")

    return _to_quote(product, cleaned)


def catalogue(*, fresh: bool = False) -> list[FundQuote]:
    """Every fund Fmarket carries, for the symbol picker to search.

    One request, and only when the user is actually looking for a symbol —
    never from a portfolio read — and remembered for `CATALOGUE_TTL_SECONDS`
    so that typing eleven characters is not eleven requests.
    """
    global _catalogue_cache
    if not fresh and _catalogue_cache is not None:
        fetched_at, cached = _catalogue_cache
        if time.monotonic() - fetched_at < CATALOGUE_TTL_SECONDS:
            return cached

    try:
        rows = _fetch_catalogue()
    except Exception as cause:  # noqa: BLE001
        raise FundError(f"Fmarket catalogue unavailable: {cause}") from cause

    quotes: list[FundQuote] = []
    for product in rows:
        code = str(product.get("code") or "")
        if not code:
            continue
        try:
            quotes.append(_to_quote(product, _public_name(code)))
        except FundError:
            continue  # a product with no NAV is not something to offer
    _catalogue_cache = (time.monotonic(), quotes)
    return quotes


def forget_catalogue() -> None:
    """Drop the remembered catalogue. For tests, and for a manual refresh."""
    global _catalogue_cache, _id_cache
    _catalogue_cache = None
    _id_cache = None


def _public_name(product_code: str) -> str:
    """The code to show for a product: the alias when there is one.

    So Dragon Capital's fund reaches the user as `DCDE`, which is what the
    certificate says, rather than as `VFMVF4`, which is what an internal
    platform calls it.
    """
    for alias, code in ALIASES.items():
        if code == product_code:
            return alias
    return product_code


def search(query: str, *, limit: int = 8) -> list[FundQuote]:
    """Funds whose code or name matches `query`, best first.

    Filtered here rather than by the API: `filter` returns the whole catalogue
    in one response, and 69 rows is smaller than the request that would ask for
    a subset of it.
    """
    text = query.strip().lower()
    if not text:
        return []

    # Substring is not an order. A query that is exactly a code — which is what
    # someone typing into a symbol field is doing — must return that code
    # first, not whichever fund's manager happens to be named after it.
    exact: list[FundQuote] = []
    partial: list[FundQuote] = []
    for fund in catalogue():
        codes = {fund.symbol.lower(), fund.product_code.lower()}
        if text in codes:
            exact.append(fund)
            continue
        haystack = f"{fund.symbol} {fund.product_code} {fund.name} {fund.owner or ''}".lower()
        if text in haystack:
            partial.append(fund)

    return (exact + partial)[:limit]
