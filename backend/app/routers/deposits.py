"""Term deposits over HTTP, including the two things that happen at maturity.

A deposit sits between the other two holdings, and the endpoints show it:

- like a market position, its value is computed rather than typed — but from
  its own terms, so nothing external can fail;
- like cash, it is denominated in one currency the user chose, so it converts
  the same way and is excluded from the total the same way when it cannot.

The two actions that only exist for a deposit are here rather than being left
to the user's arithmetic, because both of them move money between two tables
and doing that by hand is how a portfolio holds the same million twice:

- **roll over** (tất toán và gửi lại): interest becomes principal, and a new
  term begins on the day the old one ended;
- **withdraw** (tất toán): the deposit is closed and the proceeds appear as a
  cash balance, in one request.
"""

from __future__ import annotations

import datetime

from fastapi import APIRouter, Query, status
from sqlalchemy import select

from app import cash, deposits, fx, models, movements, settings_store, valuation
from app.routers.deps import DbSession, cash_report, get_or_404, refused
from app.schemas import (
    CashOut,
    DeleteOut,
    DepositCreate,
    DepositOut,
    DepositRollRequest,
    DepositUpdate,
    DepositWithdrawOut,
    DepositWithdrawRequest,
)

router = APIRouter(prefix="/api/deposits", tags=["deposits"])


def _valued(session, row: models.Deposit) -> DepositOut:
    base = settings_store.base_currency(session)
    converter = fx.Converter(session=session, base=base)
    return DepositOut.model_validate(valuation.value_term_deposit(row, converter))


def _as_date(value) -> str:
    """Store a date from either a `date` or an ISO string."""
    if isinstance(value, datetime.date):
        return value.isoformat()
    return str(value)[:10]


def _same_length_term(
    old_start: datetime.date, old_maturity: datetime.date, new_start: datetime.date
) -> datetime.date:
    """The date that makes the new term the same NUMBER OF DAYS as the old one.

    Not `new_start + (old_maturity - old_start)`: that is the same count of
    days only when the two periods happen to be the same length. A term that
    ran from 1 July to 31 December is 183 days, and 183 days from 2 January is
    4 July — while the naive subtraction, which measures the months rather than
    the days, lands on 3 July and quietly shortens every roll-over made across
    a month of different length.

    Both candidate dates are checked, because the answer is only ever one day
    either side of the arithmetic.
    """
    term_days = (old_maturity - old_start).days
    naive = new_start + (old_maturity - old_start)
    for candidate in (naive, naive - datetime.timedelta(days=1), naive + datetime.timedelta(days=1)):
        if (candidate - new_start).days == term_days:
            return candidate
    return naive


@router.get("", response_model=list[DepositOut])
def list_deposits(
    db: DbSession,
    matured: bool | None = Query(
        default=None, description="filter to the ones that have reached maturity"
    ),
) -> list[DepositOut]:
    rows = [
        _valued(db, row)
        for row in db.execute(select(models.Deposit).order_by(models.Deposit.id)).scalars()
    ]
    if matured is None:
        return rows
    return [row for row in rows if row.matured is matured]


@router.post("", response_model=DepositOut, status_code=status.HTTP_201_CREATED)
def create_deposit(payload: DepositCreate, db: DbSession) -> DepositOut:
    row = models.Deposit(
        name=payload.name.strip(),
        currency=payload.currency,
        principal=payload.principal,
        annual_rate=payload.annual_rate,
        start_date=_as_date(payload.start_date),
        maturity_date=_as_date(payload.maturity_date) if payload.maturity_date else None,
        interest_mode=payload.interest_mode,
        note=payload.note,
    )
    db.add(row)
    # Flushed, not committed: with the cash link on, the principal leaves an
    # account in the same request, and the two halves have to land together.
    db.flush()

    outcome = movements.spend(
        db,
        subject="deposit",
        action="open",
        name=row.name,
        holding_id=row.id,
        amount=float(row.principal),
        currency=row.currency,
        cash_amount=payload.cash_amount,
        occurred_on=row.start_date,
    )
    db.commit()
    db.refresh(row)

    opened = _valued(db, row)
    opened.cash = cash_report(db, outcome)
    return opened


@router.get("/{deposit_id}", response_model=DepositOut)
def read_deposit(deposit_id: int, db: DbSession) -> DepositOut:
    return _valued(db, get_or_404(db, models.Deposit, deposit_id, "Deposit"))


@router.get("/{deposit_id}/schedule", response_model=list[DepositOut])
def read_schedule(deposit_id: int, db: DbSession) -> list[DepositOut]:
    """The deposit's value from today to maturity, by the same arithmetic.

    Empty for a demand deposit, which has no maturity to draw towards.
    """
    row = get_or_404(db, models.Deposit, deposit_id, "Deposit")
    base = settings_store.base_currency(db)
    converter = fx.Converter(session=db, base=base)
    return [
        DepositOut.model_validate(
            valuation.value_term_deposit(
                row, converter, as_of=datetime.date.fromisoformat(point["as_of"])
            )
        )
        for point in deposits.schedule(row)
    ]


@router.patch("/{deposit_id}", response_model=DepositOut)
def update_deposit(deposit_id: int, payload: DepositUpdate, db: DbSession) -> DepositOut:
    """Change the terms of a deposit.

    An edited principal moves the **difference** into or out of cash: the money
    the term holds changed, so the account it came from changed with it. Rate
    and date changes move nothing — those are the contract's terms, not money.
    """
    row = get_or_404(db, models.Deposit, deposit_id, "Deposit")
    fields = payload.model_dump(exclude_unset=True)
    cash: movements.Outcome | None = None

    if "principal" in fields:
        before = float(row.principal or 0.0)
        after = fields["principal"]
        if after is not None and float(after) != before:
            cash = movements.adjust(
                db,
                subject="deposit",
                name=(fields.get("name") or row.name),
                holding_id=row.id,
                delta=float(after) - before,
                currency=(fields.get("currency") or row.currency),
                    )

    if "name" in fields and fields["name"]:
        fields["name"] = fields["name"].strip()
    if "start_date" in fields and fields["start_date"] is not None:
        fields["start_date"] = _as_date(fields["start_date"])
    if "maturity_date" in fields and fields["maturity_date"] is not None:
        fields["maturity_date"] = _as_date(fields["maturity_date"])

    for key, value in fields.items():
        setattr(row, key, value)

    start = row.start_date
    if row.maturity_date is not None and row.maturity_date < start:
        raise refused("maturity_date cannot be before start_date")

    row.updated_at = models.utcnow_iso()
    db.commit()
    db.refresh(row)

    updated = _valued(db, row)
    if cash is not None:
        updated.cash = cash_report(db, cash)
    return updated


@router.delete("/{deposit_id}", response_model=DeleteOut)
def delete_deposit(deposit_id: int, db: DbSession) -> DeleteOut:
    """Remove a deposit, giving back what it still had in a cash account.

    Deleting is not withdrawing: nothing is paid out and no interest is
    credited. What comes back is the principal the account actually paid and
    has not already had returned — which is the honest answer for "I recorded
    this by mistake" as well as for "it moved and I will fix the cash myself".
    """
    row = get_or_404(db, models.Deposit, deposit_id, "Deposit")
    outcome = movements.refund(
        db, subject="deposit", holding_id=row.id, name=row.name
    )
    db.delete(row)
    db.commit()
    return DeleteOut(removed_id=deposit_id, cash=cash_report(db, outcome))


@router.post("/{deposit_id}/roll", response_model=DepositOut)
def roll_deposit(
    deposit_id: int, payload: DepositRollRequest, db: DbSession
) -> DepositOut:
    """Roll a matured deposit into a new term, in place.

    In place rather than as a new record: the user's list should show what they
    hold now, not every term they have ever held. What the roll-over must not
    lose is the interest — it becomes part of the new principal, which is
    exactly what the bank does and exactly what would otherwise silently
    disappear from the portfolio.
    """
    row = get_or_404(db, models.Deposit, deposit_id, "Deposit")
    computed = deposits.value_deposit(row)

    if not computed.matured and row.maturity_date is not None:
        raise refused(
            "this deposit has not reached maturity; rolling it over early would "
            "invent interest the contract does not pay"
        )

    old_start = datetime.date.fromisoformat(row.start_date)
    old_maturity = (
        datetime.date.fromisoformat(row.maturity_date) if row.maturity_date else None
    )

    new_start = payload.start_date or old_maturity or datetime.date.today()
    if payload.maturity_date is not None:
        new_maturity = payload.maturity_date
    elif old_maturity is not None:
        new_maturity = _same_length_term(old_start, old_maturity, new_start)
    else:
        new_maturity = None

    row.principal = payload.principal if payload.principal is not None else computed.value
    if payload.annual_rate is not None:
        row.annual_rate = payload.annual_rate
    row.start_date = _as_date(new_start)
    row.maturity_date = _as_date(new_maturity) if new_maturity else None
    if payload.note is not None:
        row.note = payload.note
    row.updated_at = models.utcnow_iso()

    db.commit()
    db.refresh(row)
    return _valued(db, row)


@router.post("/{deposit_id}/withdraw", response_model=DepositWithdrawOut)
def withdraw_deposit(
    deposit_id: int, payload: DepositWithdrawRequest, db: DbSession
) -> DepositWithdrawOut:
    """Close a deposit and put the money back into cash, in one request.

    The deposit is deleted rather than kept at zero: a closed term is not
    something the user holds, and a list of zeroed rows is a list of things to
    scroll past.

    **Where it lands is not a decision.** The pot of the deposit's own currency
    is the only cash there is (`app.cash`), so the proceeds accumulate there —
    a term deposit is the same money coming back, not a new pile of it. This is
    the one movement that happens whether or not the cash link is on: with the
    link off the balance still has to change, and there is no longer an account
    to invent for it. Leaving the money arriving with no line of history would
    be a balance that changed for no stated reason, which is the thing the
    history exists to prevent.
    """
    row = get_or_404(db, models.Deposit, deposit_id, "Deposit")
    computed = deposits.value_deposit(row)
    amount = payload.balance if payload.balance is not None else computed.value

    outcome = movements.receive(
        db,
        subject="deposit",
        action="close",
        name=row.name,
        holding_id=row.id,
        amount=amount,
        currency=row.currency,
        occurred_on=models.today_iso(),
        note=row.note,
        # The one movement that ignores the switch: the money is arriving and
        # the pot is the only place it can go.
        force=True,
    )
    db.delete(row)
    db.commit()

    account = (
        db.get(models.CashAccount, outcome.movement.account_id)
        if outcome.movement is not None
        else cash.pot(db, row.currency)
    )

    base = settings_store.base_currency(db)
    converter = fx.Converter(session=db, base=base)
    return DepositWithdrawOut(
        closed_deposit_id=deposit_id,
        account=CashOut.model_validate(valuation.value_cash(account, converter)),
        amount=amount,
        cash=cash_report(db, outcome),
    )
