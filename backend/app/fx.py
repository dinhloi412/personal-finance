"""Foreign exchange, and the one rule that keeps a total honest.

Every total in this app is in ONE currency — the base, named in `settings` —
and anything in another currency is divided by a rate before it is added. The
conversion is not a detail: adding 1 000 000 VND to 100 USD without one gives
1 000 100 of nothing.

Rules this module enforces:

1. **A rate is not a number without a base.** `fx_rates` is keyed by
   (base, currency, day). The feed never lists its own base among its rates, so
   a row that did not say which base it was fetched for would be read against
   whichever base asked next.
2. **A missing rate converts to None, never to 1.0.** A currency we cannot
   convert is excluded from the total and reported, because a total that is
   quietly short is worse than one that is visibly incomplete.
3. **A stale rate is labelled.** When the feed is unreachable, the newest
   stored row keeps serving with its day attached, and the response says
   `stale: true`. Seed rows (the constant rate a fresh install starts with) are
   `stale` too.

Feed: <https://open.er-api.com/v6/latest/USD> — no key, and it carries VND,
which the ECB feed does not.
"""

from __future__ import annotations

import datetime
import json
import urllib.request
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.money import BASE_CURRENCIES, CURRENCIES, BaseCurrency

FX_URL = "https://open.er-api.com/v6/latest/{base}"

#: The rate a database starts with, so the app is usable the moment it opens
#: and offline from the first second. Roughly the long-run USD/VND level; it is
#: marked `seed` in the database and `stale` in every response, so a user who
#: never refreshes is never misled about which number they are reading.
SEED_USD_VND = 26_000.0

#: Where a rate came from, kept so the UI can say whether a figure is a
#: published rate or a placeholder.
SOURCE_FEED = "feed"
SOURCE_SEED = "seed"


@dataclass(frozen=True)
class Rate:
    """One rate and everything needed to be honest about it.

    `rate` is units of `currency` per 1 unit of `base`, so the conversion is a
    division: `amount_in_base = amount / rate`.
    """

    currency: str
    rate: float
    as_of: str
    source: str
    stale: bool

    def to_base(self, amount: float) -> float:
        return amount / self.rate


# --------------------------------------------------------------------------
# Network — the only function here that touches the wire.
# --------------------------------------------------------------------------


def _fetch_rates(base: str) -> dict:
    """Raw latest rates for `base`. Isolated so tests replace this one name."""
    request = urllib.request.Request(
        FX_URL.format(base=base),
        headers={"User-Agent": "SoTaiSan/0.1 (personal asset tracker)"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


# --------------------------------------------------------------------------
# Seeding and refreshing
# --------------------------------------------------------------------------


def seed_rates(session: Session, base: str, day: str | None = None) -> None:
    """Make sure `base` has a rate for every other supported currency.

    A fresh database must be able to convert something the second it opens,
    even with no network. So: ask the feed for today's rate, and for anything
    still missing write the placeholder. Nothing already stored is touched, so
    a real rate learned earlier is never replaced by the placeholder on the
    next start.
    """
    day = day or _today()
    refreshed = refresh_rates(session, base)
    stored = set(refreshed.get("stored") or [])

    for currency in CURRENCIES:
        if currency == base or currency in stored:
            continue  # a base is 1 in itself, and a real rate beats a seed
        rate = _cross_rate(base, currency)
        if rate is None:
            continue
        _upsert(
            session,
            base=base,
            currency=currency,
            day=day,
            rate=rate,
            source=SOURCE_SEED,
        )
    session.commit()


def _cross_rate(base: str, currency: str) -> float | None:
    """The seeded rate of `currency` per 1 `base`, through USD."""
    if base == "USD":
        return SEED_USD_VND if currency == "VND" else None
    if base == "VND":
        return 1.0 / SEED_USD_VND if currency == "USD" else None
    return None


def refresh_rates(session: Session, base: str) -> dict:
    """Fetch today's rates for `base` and store a row per supported currency.

    Returns a small report rather than raising: an unreachable feed must leave
    the app working on what it already knows, and must say so.
    """
    today = _today()
    try:
        payload = _fetch_rates(base)
    except Exception as cause:  # noqa: BLE001 — any failure is "no new rates"
        return {"ok": False, "error": str(cause), "stored": [], "as_of": today}

    rates = payload.get("rates") or {}
    if payload.get("result") != "success" and not rates:
        return {
            "ok": False,
            "error": f"feed answered {payload.get('result')!r}",
            "stored": [],
            "as_of": today,
        }

    stored: list[str] = []
    for currency in CURRENCIES:
        if currency == base:
            continue
        value = rates.get(currency)
        if not isinstance(value, (int, float)) or value <= 0:
            continue
        _upsert(session, base=base, currency=currency, day=today, rate=float(value))
        stored.append(currency)
    session.commit()
    return {"ok": True, "error": None, "stored": stored, "as_of": today}


def _upsert(
    session: Session,
    *,
    base: str,
    currency: str,
    day: str,
    rate: float,
    source: str = SOURCE_FEED,
) -> None:
    """Write one day's rate, replacing an earlier row for the same day.

    `source` defaults to the feed because that is who usually calls this; the
    seed passes its own name so the placeholder is never mistaken for a quote.
    """
    row = session.get(models.FxRate, (base, currency, day))
    if row is None:
        session.add(
            models.FxRate(
                base=base,
                currency=currency,
                as_of=day,
                rate=rate,
                source=source,
            )
        )
        return
    row.rate = rate
    row.source = source
    row.fetched_at = models.utcnow_iso()


# --------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------


def rate_on(session: Session, base: str, currency: str, day: str | None = None) -> Rate:
    """The rate in force on `day`: that day's, else the newest older one.

    A rate published after the day asked for is never used: pricing a total
    fixed on Monday with Tuesday's rate dates it on a day it did not happen.
    """
    day = day or _today()
    if currency == base:
        return Rate(currency=currency, rate=1.0, as_of=day, source="base", stale=False)

    rows = list(
        session.execute(
            select(models.FxRate)
            .where(
                models.FxRate.base == base,
                models.FxRate.currency == currency,
                models.FxRate.as_of <= day,
            )
            .order_by(models.FxRate.as_of.desc())
            .limit(1)
        ).scalars()
    )
    if not rows:
        # Nothing stored for or before that day. A rate from after it is still
        # better than refusing to show a number, as long as it is labelled.
        later = list(
            session.execute(
                select(models.FxRate)
                .where(
                    models.FxRate.base == base,
                    models.FxRate.currency == currency,
                )
                .order_by(models.FxRate.as_of.asc())
                .limit(1)
            ).scalars()
        )
        if not later:
            return Rate(
                currency=currency,
                rate=float("nan"),
                as_of=day,
                source="missing",
                stale=True,
            )
        row = later[0]
    else:
        row = rows[0]

    return Rate(
        currency=currency,
        rate=row.rate,
        as_of=row.as_of,
        source=row.source,
        # Stale means "not published for the day asked": the placeholder always
        # is, and so is any rate that had to come from another day.
        stale=row.source == SOURCE_SEED or row.as_of != day,
    )


@dataclass
class Converter:
    """Converts amounts into one base, and remembers what it used.

    Constructed per request with the session and the base in force. `used`
    collects the rates actually applied, so a response can hand the reader the
    rates behind its totals instead of a number to be trusted blindly.
    """

    session: Session
    base: str
    day: str | None = None
    #: Filled as conversions happen; not part of the constructor.
    used: dict[str, Rate] = field(default_factory=dict, init=False)

    def rate_for(self, currency: str | None) -> Rate | None:
        """The rate for `currency`, or None when it cannot be converted."""
        if not currency:
            return None
        code = currency.upper()
        if code not in CURRENCIES:
            return None
        # The base is 1 in itself by definition. Recording it as a "rate used"
        # would put a line in the report saying the portfolio was converted at
        # 1.0, which is not a conversion.
        if code == self.base:
            return Rate(
                currency=code, rate=1.0, as_of=self.day or _today(), source="base", stale=False
            )
        cached = self.used.get(code)
        if cached is not None:
            return cached
        found = rate_on(self.session, self.base, code, self.day)
        if found.rate != found.rate or found.rate <= 0:  # NaN or nonsense
            return None
        self.used[code] = found
        return found

    def to_base(self, amount: float | None, currency: str | None) -> float | None:
        """`amount` in the base currency, or None if it cannot be converted.

        None is a real answer here and every caller must handle it: it is what
        keeps an unconvertible position out of a total instead of into it.
        """
        if amount is None:
            return None
        rate = self.rate_for(currency)
        if rate is None:
            return None
        return amount / rate.rate

    def report(self) -> list[dict]:
        """The rates used so far, for the response that carries the totals."""
        return [
            {
                "currency": rate.currency,
                "rate": rate.rate,
                "as_of": rate.as_of,
                "source": rate.source,
                "stale": rate.stale,
            }
            for rate in sorted(self.used.values(), key=lambda r: r.currency)
        ]


def _today() -> str:
    return datetime.datetime.now(datetime.timezone.utc).date().isoformat()


def supported() -> tuple[BaseCurrency, ...]:
    """The bases this app can total in. Here so callers need not import two
    modules to ask one question."""
    return BASE_CURRENCIES
