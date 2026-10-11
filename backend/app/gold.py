"""Vietnamese gold prices, from Bảo Tín Minh Châu's public price API.

Vietnam's gold price is not the world price. SJC bars and 9999 rings trade at a
domestic premium fixed by supply, by the State Bank's import rules and by the
shops themselves, and the shops are where the price lives. So this module reads
a Vietnamese shop, not a world feed:

    https://api.btmc.vn/api/BTMCAPI/getpricebtmc?key=<public key>

A plain JSON answer, no account, and the prices are for today — mua (the shop
buys) and bán (the shop sells) for 21 products, each stamped with the minute it
was updated.

Four things about that payload shape the code, and each was found by looking at
it rather than by assuming:

**1. One unit is published per product line, and the rest are arithmetic.**
BTMC quotes `VÀNG MIẾNG SJC` per lượng and `VÀNG NGUYÊN LIỆU` per chỉ, and the
payload does not say which. The unit is read from the product's own name
(`... 5 LƯỢNG ...`, `... 0,5 KG ...`, or nothing at all, which for a bar means
one lượng), and everything is normalised to **per chỉ** — the unit Vietnamese
gold is actually bought and sold in. 1 lượng is 10 chỉ by definition, so this
is division, not conversion.

**2. Which price is the holding worth?** A shop sells at `bán` and buys at
`mua`, and the difference is the spread — a real cost, not a rounding error. An
app that valued gold at the sell price would show a profit the moment you
walked out of the shop. The default is therefore **`mua`**, what you would get
for it today, and the interface says which of the two it used.

**3. The payload is a list of one-key objects, not a list of rows.** Every
field is suffixed with the row number — `@n_1`, `@pb_1`, `@d_1`, then `@n_2`,
`@pb_2`, `@d_2` — so a row is read by its own `@row` number rather than by
field name. Parsing it positionally produces a table of nothings.

**4. Products come and go, and names are not identifiers.** `VÀNG MIẾNG SJC`
today may be `VÀNG SJC 1 LƯỢNG` next year. A stored holding therefore points at
a normalised *key* derived from the product's name, and a key that no longer
appears is reported as unpriced rather than silently valued at whatever row
happens to be first.
"""

from __future__ import annotations

import datetime
import json
import re
import time
import unicodedata
import urllib.request
from dataclasses import dataclass

from app import net
from app.money import CHI_IN_GRAMS, GRAMS_PER_UNIT

#: The public key the shop's own website uses. It is in their page source; it
#: is not a secret and it is not an account. Named here so that if it ever
#: changes, it changes in one place and the failure is a clear 403.
API_KEY = "3kd8ub1llcg9t45hnoh8hmn7t5gc9mtq"
API_URL = f"https://api.btmc.vn/api/BTMCAPI/getpricebtmc?key={API_KEY}"

USER_AGENT = "SoTaiSan/0.1 (personal asset tracker; one request a day)"
TIMEOUT_SECONDS = 20

#: How long a fetched price list stays good. Gold moves a few times a day, so a
#: quarter of an hour is fresh for a tracker and keeps this to a handful of
#: requests a day.
PRICE_TTL_SECONDS = 15 * 60

#: Which of the two published prices a holding is valued at.
PRICE_BASIS_BUY = "buy"
PRICE_BASIS_SELL = "sell"
PRICE_BASES = (PRICE_BASIS_BUY, PRICE_BASIS_SELL)

#: The currency this shop quotes in, and the unit everything is normalised to.
VND = "VND"
UNIT = "chi"


class GoldError(Exception):
    """The price list could not be fetched, or nothing in it matches."""


#: The payload carries the shop's silver lines in the same list. They are not
#: gold, and offering someone `BẠC THỎI 2025` when they asked for gold would be
#: a worse failure than offering nothing. Matched on the product name only:
#: `Ag 999` appears in some of them and not others.
_SILVER_MARKER = "bac"


def is_gold(raw_name: str) -> bool:
    """True when this product line is gold rather than silver.

    `BẠC` (silver) and `VÀNG` (gold) are one letter apart before the accents
    are stripped, which is why this is checked rather than assumed.
    """
    return _SILVER_MARKER not in _strip_accents(raw_name).split()[:3]


@dataclass(frozen=True)
class GoldPrice:
    """One product's price, normalised to a single unit."""

    key: str
    name: str
    #: Price for ONE `unit`, in VND.
    buy: float
    sell: float
    unit: str
    #: When the shop last changed it, as the shop states it.
    updated_at: str
    #: The shop's own row, kept so the interface can show the published figure
    #: beside the per-unit one derived from it.
    raw_name: str

    def price(self, basis: str = PRICE_BASIS_BUY) -> float:
        return self.sell if basis == PRICE_BASIS_SELL else self.buy


# --------------------------------------------------------------------------
# Network — the only function here that touches the shop.
# --------------------------------------------------------------------------


def _fetch_prices() -> dict:
    """The raw payload. Isolated so tests replace this one name."""
    request = urllib.request.Request(
        API_URL,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    # Through `app.net`, not `urlopen`: this server does not send its
    # intermediate certificate, so the platform trust store rejects it.
    with net.open_url(request, timeout=TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


# --------------------------------------------------------------------------
# Pure helpers — the parsing, which is where the payload's shape is absorbed.
# --------------------------------------------------------------------------


def _strip_accents(text: str) -> str:
    """`VÀNG MIẾNG SJC` -> `vang mieng sjc`, for matching rather than display."""
    lowered = text.lower().replace("đ", "d")
    return "".join(
        character
        for character in unicodedata.normalize("NFD", lowered)
        if unicodedata.category(character) != "Mn"
    )


def normalise_key(name: str) -> str:
    """A stable key for a product, derived from its name.

    The brand in the trailing parentheses is what separates two otherwise
    identical lines — `NHẪN TRÒN TRƠN (Vàng Rồng Thăng Long)` against `VÀNG
    MIẾNG SJC (Vàng SJC)` — so it is kept. Punctuation and accents are not,
    because they change when someone edits the listing.
    """
    return re.sub(r"[^a-z0-9]+", "-", _strip_accents(name)).strip("-")


#: Weight mentioned inside a product name. The shop writes `1 LƯỢNG`,
#: `5 LƯỢNG`, `10 LƯỢNG`, `0,5 KG`, `500 GRAM`.
#:
#: `(?<![a-z])` on the unit is load-bearing and was added after a real bug: the
#: word `LƯỢNG` ends in `g`, so without it `5 LƯỢNG` parsed as "5 grams" and a
#: bar came out ten times too light. A unit letter that is the tail of a word is
#: not a unit.
_WEIGHT_PATTERN = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(?<![a-z])(kg|kilogram|gram|g|luong|chi|phan)\b",
    re.IGNORECASE,
)

#: Grams in each unit the listings mention. `luong` and `chi` come from the
#: shared vocabulary, so a lượng is ten chỉ everywhere in the app.
_LISTING_UNITS: dict[str, float] = {
    "kg": 1000.0,
    "kilogram": 1000.0,
    "gram": 1.0,
    "g": 1.0,
    "luong": GRAMS_PER_UNIT["luong"],
    "chi": CHI_IN_GRAMS,
    "phan": CHI_IN_GRAMS / 10,
}

#: A product name with no weight is a bar priced per lượng — that is how the
#: shop lists `VÀNG MIẾNG SJC` and `NHẪN TRÒN TRƠN`.
_DEFAULT_WEIGHT_IN_CHI = 10.0


def weight_in_chi(raw_name: str) -> float | None:
    """How many chỉ the price in `raw_name` is for.

    None when the name states a weight this module cannot read — a reason to
    refuse the row rather than to guess. A price divided by the wrong weight is
    wrong by a factor of ten, and a factor of ten in gold is not a rounding
    error.
    """
    match = _WEIGHT_PATTERN.search(_strip_accents(raw_name))
    if match is None:
        return _DEFAULT_WEIGHT_IN_CHI
    amount = float(match.group(1).replace(",", "."))
    grams = _LISTING_UNITS.get(match.group(2).lower())
    if grams is None or amount <= 0:
        return None
    return amount * grams / CHI_IN_GRAMS


def _as_money(value: object) -> float | None:
    """A price as a number, or None when the shop published a dash or a zero.

    A zero in this payload means "not trading this line today" — `VÀNG NGUYÊN
    LIỆU` has `bán = 0` — and a zero that reached a portfolio would value a
    holding at nothing.
    """
    if value is None:
        return None
    text = str(value).strip()
    digits = re.sub(r"[^\d]", "", text)
    if not digits:
        return None
    number = float(digits)
    return number if number > 0 else None


def _brand(raw_name: str) -> str:
    """The trailing parenthetical: the brand, which is what a person says."""
    match = re.search(r"\(([^)]+)\)\s*$", raw_name.strip())
    return match.group(1).strip() if match else ""


def display_name(raw_name: str) -> str:
    """A short readable name: `VÀNG MIẾNG SJC`.

    The payload repeats the brand in a trailing parenthesis, which reads as
    noise beside a name that already contains it.
    """
    return re.sub(r"\s*\([^)]*\)\s*$", "", raw_name.strip()).strip()


#: How far a line's price per chỉ may sit from the middle of the list before
#: the weight it was divided by is treated as wrong. A gold line's price does
#: not differ between product lines by more than a few per cent — the whole
#: list is one metal on one day — so a line an order of magnitude away from the
#: middle was divided by the wrong weight. Set deliberately wide: this is a
#: sanity check, not a price model.
_PLAUSIBLE_RATIO = 4.0


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def parse_payload(payload: dict) -> list[GoldPrice]:
    """Every product in the payload, normalised to a price per chỉ.

    Rows are read by their own number because that is how the payload is keyed.
    A row that cannot be read — no weight, no price — is skipped rather than
    guessed at.

    One more check, which exists because of a real line: `ĐỒNG XU VRTL 0.1` is
    a coin whose name states no unit, so it is read as the default one lượng and
    its price comes out at 139 600 ₫ a chỉ — a tenth of what a chỉ of gold
    costs, because the coin is really a tenth of a lượng and the shop quotes it
    per coin. Rather than guess the unit from a name that does not state one,
    every line is compared against the MIDDLE of the list: gold is one metal on
    one day, so its lines cannot differ by an order of magnitude, and a line
    that does was divided by the wrong weight and is dropped.
    """
    rows = (payload.get("DataList") or {}).get("Data") or []
    prices: list[GoldPrice] = []

    for row in rows:
        number = str(row.get("@row") or "").strip()
        if not number:
            continue
        raw_name = str(row.get(f"@n_{number}") or "").strip()
        if not raw_name or not is_gold(raw_name):
            continue

        weight = weight_in_chi(raw_name)
        if weight is None:
            continue

        buy = _as_money(row.get(f"@pb_{number}"))
        sell = _as_money(row.get(f"@ps_{number}"))
        # A line with neither price is not a price. A line with only one is
        # still useful, so the other takes the same figure rather than the row
        # being dropped.
        if buy is None and sell is None:
            continue
        buy = buy if buy is not None else sell
        sell = sell if sell is not None else buy

        name = display_name(raw_name)
        brand = _brand(raw_name)
        label = f"{name} ({brand})" if brand and brand.lower() not in name.lower() else name

        prices.append(
            GoldPrice(
                key=normalise_key(raw_name),
                name=label,
                buy=buy / weight,
                sell=sell / weight,
                unit=UNIT,
                updated_at=str(row.get(f"@d_{number}") or ""),
                raw_name=raw_name,
            )
        )

    if not prices:
        return []

    middle = _median([product.buy for product in prices])
    if middle <= 0:
        return prices

    return [
        product
        for product in prices
        if 1 / _PLAUSIBLE_RATIO <= product.buy / middle <= _PLAUSIBLE_RATIO
    ]


_cache: tuple[float, list[GoldPrice]] | None = None


def forget_cache() -> None:
    """Drop the remembered prices. For tests, and for a manual refresh."""
    global _cache
    _cache = None


def prices(*, fresh: bool = False) -> list[GoldPrice]:
    """Today's price list, from the cache when it is recent enough.

    One request per `PRICE_TTL_SECONDS` at most, however many holdings point at
    it: they all price off the same list.
    """
    global _cache
    if not fresh and _cache is not None:
        fetched_at, cached = _cache
        if time.monotonic() - fetched_at < PRICE_TTL_SECONDS:
            return cached

    try:
        payload = _fetch_prices()
    except Exception as cause:  # noqa: BLE001 — any failure is "no price list"
        raise GoldError(f"the gold price list is unreachable: {cause}") from cause

    parsed = parse_payload(payload)
    if not parsed:
        raise GoldError("the gold price list came back empty")
    _cache = (time.monotonic(), parsed)
    return parsed


def catalogue(*, fresh: bool = False) -> list[GoldPrice]:
    """Every product the shop publishes, for the picker."""
    return prices(fresh=fresh)


def find(key: str, *, fresh: bool = False) -> GoldPrice:
    """One product by its normalised key.

    Raises rather than returning the nearest match: a holding must not be
    silently re-pointed at another product line because the shop renamed one.
    The caller reports it as unpriced and the user picks again.
    """
    wanted = key.strip()
    for product in prices(fresh=fresh):
        if product.key == wanted:
            return product
    raise GoldError(f"the gold price list has no product {key!r}")


def search(query: str, *, limit: int = 8) -> list[GoldPrice]:
    """Products whose name or key contains `query`, best first."""
    text = _strip_accents(query.strip())
    if not text:
        return []
    # A query that is part of the key is what someone typing "sjc" is doing;
    # those come before a fund that merely mentions it in passing.
    strong = [p for p in catalogue() if text in p.key]
    weak = [p for p in catalogue() if text not in p.key and text in _strip_accents(p.name)]
    return (strong + weak)[:limit]


def updated_on(product: GoldPrice) -> str:
    """The date the shop states for its price, as `YYYY-MM-DD` when readable.

    The payload writes `11/10/2026 10:42`. The date is what a price cache
    wants; the time is dropped rather than turned into an instant in a timezone
    the shop never stated.
    """
    match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", product.updated_at)
    if not match:
        return datetime.date.today().isoformat()
    day, month, year = (int(part) for part in match.groups())
    try:
        return datetime.date(year, month, day).isoformat()
    except ValueError:
        return datetime.date.today().isoformat()


def default_key() -> str:
    """The product to offer first: SJC bars, which is what most people mean.

    Falls back to the first product the shop lists, so a rename on their side
    degrades to "something is still chosen" rather than to an empty picker.
    """
    listed = catalogue()
    for product in listed:
        if "sjc" in product.key:
            return product.key
    return listed[0].key if listed else ""
