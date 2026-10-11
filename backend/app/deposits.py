"""Term deposits: the interest arithmetic, and the one place it is written.

A term deposit is the third kind of thing this app holds, and it is different
from the other two in the direction that matters:

- a market position's value comes from **outside** (a quote we did not compute);
- cash's value comes from **the user** (a balance they counted);
- a deposit's value comes from **the agreement** (a principal, a rate, and the
  number of days it has been running).

So this module is where the app stops recording and starts deriving, and it is
worth being explicit about every choice in it:

**Simple interest, on actual days, over a 365-day year.** A Vietnamese term
deposit quotes a year rate and, at maturity, pays `principal × rate × days/365`.
It does not compound daily, and modelling it as though it did would overstate
the figure the user is about to compare with their bank statement — which is
the one comparison this number has to survive.

**Interest stops at maturity.** After the maturity date the money is not
earning the contract rate any more: it is sitting in the account, and whatever
it earns from then on is a new agreement. Carrying the old rate forward would
invent income, so `value()` freezes at the contractual payout and the record
says `matured: true` — visibly, so the user knows there is a decision to make.

**A demand deposit never matures.** `maturity_date = None` means không kỳ hạn:
no end date, so interest keeps accruing and the value keeps growing. That is
the one case where a value can rise without anyone doing anything.
"""

from __future__ import annotations

import datetime
from dataclasses import asdict, dataclass

from app.money import DAYS_IN_YEAR


def _to_date(value: str | None) -> datetime.date | None:
    """Parse a stored `YYYY-MM-DD`, or None if there is nothing to parse."""
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(value[:10])
    except ValueError:
        return None


def days_between(start: str | None, end: datetime.date) -> int:
    """Whole days from `start` to `end`, never negative.

    A start date in the future is treated as zero days rather than a negative
    term: the money has not been lent yet, so no interest has been earned, and
    a negative figure would quietly subtract from the portfolio.
    """
    began = _to_date(start)
    if began is None:
        return 0
    return max((end - began).days, 0)


@dataclass(frozen=True)
class DepositValue:
    """One deposit, as of a day: what it is worth and why.

    Every field is derived from the row and the date, so the same row read on
    two days gives two honest answers rather than one cached one.
    """

    id: int
    name: str
    currency: str
    principal: float
    annual_rate: float
    start_date: str
    maturity_date: str | None
    interest_mode: str
    note: str | None

    #: The day the arithmetic was done for.
    as_of: str
    #: Days of interest counted (up to today, or up to maturity once matured).
    days_accrued: int
    #: Interest earned so far, in the deposit's own currency.
    interest_accrued: float
    #: principal + interest_accrued, in the deposit's own currency.
    value: float

    #: True when the maturity date has been reached: interest has stopped and
    #: the money needs a decision (roll it over, or take it out).
    matured: bool
    #: Days until maturity; null for a demand deposit or once matured.
    days_remaining: int | None
    #: What it will be worth at maturity (principal + full-term interest);
    #: equal to `value` once matured.
    value_at_maturity: float

    #: The same two figures in the base currency. Null when unconvertible.
    value_base: float | None = None
    interest_base: float | None = None
    reason: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def value_deposit(
    row,
    *,
    as_of: datetime.date | None = None,
) -> DepositValue:
    """Compute one deposit's accrued interest and value, with no conversion.

    Conversion is deliberately not done here: this function is pure arithmetic
    over a row and a date, which is what makes it testable without a session
    and a rate table. The caller adds the base-currency figures.
    """
    day = as_of or datetime.date.today()
    maturity = _to_date(row.maturity_date)

    total_days = days_between(row.start_date, day)
    # Interest accrues up to today, or up to maturity — whichever came first.
    if maturity is not None and day > maturity:
        accrued_days = days_between(row.start_date, maturity)
    else:
        accrued_days = total_days

    interest = row.principal * (row.annual_rate / 100.0) * accrued_days / DAYS_IN_YEAR

    matured = maturity is not None and day >= maturity

    if maturity is None:
        days_remaining: int | None = None
        full_term_days = accrued_days
    else:
        days_remaining = None if matured else max((maturity - day).days, 0)
        full_term_days = days_between(row.start_date, maturity)

    at_maturity = row.principal * (
        1.0 + (row.annual_rate / 100.0) * full_term_days / DAYS_IN_YEAR
    )

    return DepositValue(
        id=row.id,
        name=row.name,
        currency=row.currency,
        principal=float(row.principal),
        annual_rate=float(row.annual_rate),
        start_date=row.start_date,
        maturity_date=row.maturity_date,
        interest_mode=row.interest_mode,
        note=row.note,
        as_of=day.isoformat(),
        days_accrued=accrued_days,
        interest_accrued=interest,
        value=float(row.principal) + interest,
        matured=matured,
        days_remaining=days_remaining,
        value_at_maturity=at_maturity,
    )


def schedule(row, *, as_of: datetime.date | None = None, steps: int = 12) -> list[dict]:
    """How this deposit's value grows from now to maturity.

    Empty for a demand deposit, which has no maturity to draw towards. The
    points are computed by the same function that values it today, so the
    projection cannot disagree with the figure on the page.
    """
    maturity = _to_date(row.maturity_date)
    if maturity is None:
        return []

    day = as_of or datetime.date.today()
    began = _to_date(row.start_date) or day
    # A term that has already ended still has a projection worth returning: it
    # is the one point that says what the money became. Saying "no schedule"
    # for it would be a gap exactly where the user wants the answer.
    start = min(max(day, began), maturity)
    span = (maturity - start).days
    if span <= 0:
        return [value_deposit(row, as_of=maturity).as_dict()]

    step = max(span // steps, 1)
    points: list[dict] = []
    cursor = start
    while cursor < maturity:
        points.append(value_deposit(row, as_of=cursor).as_dict())
        cursor += datetime.timedelta(days=step)
    points.append(value_deposit(row, as_of=maturity).as_dict())
    return points
