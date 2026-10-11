"""Cash over HTTP: the two pots, money in and out, and editing what is in them.

**One pot per currency**, made by `app.cash` and never created or removed over
HTTP. There is no "add a cash account" and no "delete" because there is nothing
to add them to: the money accumulates in đồng and in dollars, which is what
having a bank balance means.

Three ways a balance changes, and every one of them writes a line:

- **`POST /{id}/entry`** — money the user says went in or came out, with a
  reason: a salary, a bill, a gift. Not a trade, and not a category.
- **`PATCH /{id}`** — the manual update this app is built around: the user
  counts their money and types the number. The difference is written down as an
  adjustment, so the balance stays the sum of its history.
- **a trade**, through `/api/assets`, `/api/deposits` and `/api/gold`, which is
  where `app.movements` comes in.

The *history* is read from `/api/portfolio`, with every other figure, rather
than from a page of its own.
"""

from __future__ import annotations

from fastapi import APIRouter

from app import cash, fx, models, movements, settings_store, valuation
from app.routers.deps import DbSession, cash_report, get_or_404
from app.schemas import CashEntryOut, CashEntryRequest, CashOut, CashUpdate

router = APIRouter(prefix="/api/cash", tags=["cash"])


def _valued(session, account: models.CashAccount) -> CashOut:
    base = settings_store.base_currency(session)
    converter = fx.Converter(session=session, base=base)
    return CashOut.model_validate(valuation.value_cash(account, converter))


@router.get("", response_model=list[CashOut])
def list_cash(db: DbSession) -> list[CashOut]:
    """Both pots, đồng first.

    Reading makes sure they exist: a wipe empties the table, and a page that
    then showed no cash at all would be missing the one thing it is for.
    """
    cash.ensure_pots(db)
    return [_valued(db, account) for account in cash.pots(db)]


@router.get("/{account_id}", response_model=CashOut)
def read_cash(account_id: int, db: DbSession) -> CashOut:
    return _valued(db, get_or_404(db, models.CashAccount, account_id, "Cash pot"))


@router.post("/{account_id}/entry", response_model=CashEntryOut)
def write_entry(
    account_id: int, payload: CashEntryRequest, db: DbSession
) -> CashEntryOut:
    """Record money going into a balance, or coming out of it.

    This is the one place the app asks *why* money moved without asking what it
    was for in a way it could total up later: a reason is text, and it is stored
    as one. The balance and the line are written together by `app.movements`, so
    the page's claim that a balance is the sum of its history stays true.
    """
    account = get_or_404(db, models.CashAccount, account_id, "Cash pot")
    signed = payload.amount if payload.direction == "in" else -payload.amount

    outcome = movements.entry(
        db,
        account=account,
        amount=signed,
        action=payload.direction,
        occurred_on=payload.occurred_on.isoformat() if payload.occurred_on else None,
        note=payload.note,
    )
    db.commit()
    db.refresh(account)

    base = settings_store.base_currency(db)
    converter = fx.Converter(session=db, base=base)
    return CashEntryOut(
        account=CashOut.model_validate(valuation.value_cash(account, converter)),
        cash=cash_report(db, outcome),
    )


@router.patch("/{account_id}", response_model=CashOut)
def update_cash(account_id: int, payload: CashUpdate, db: DbSession) -> CashOut:
    """Edit a balance — the manual update, in one request.

    `balance_at` is stamped to today whenever the balance itself changes, so
    the page can say how old each figure is. Renaming a pot does not restamp it:
    the money did not move.

    A changed balance writes the **difference** down as an adjustment, because
    the page prints one figure and claims it is the sum of the lines under it.
    Counting your money and finding a different number is a real event — it is
    how this app is meant to be used — and an event with no line is exactly the
    gap the history was added to close.
    """
    account = get_or_404(db, models.CashAccount, account_id, "Cash pot")
    fields = payload.model_dump(exclude_unset=True)

    if "name" in fields and fields["name"]:
        fields["name"] = fields["name"].strip()

    counted = fields.pop("balance", None)
    difference = 0.0
    if counted is not None and counted != account.balance:
        difference = counted - float(account.balance or 0.0)

    for key, value in fields.items():
        setattr(account, key, value)

    outcome = movements.Outcome(skipped=movements.SKIP_NO_AMOUNT)
    if difference:
        outcome = movements.entry(
            db,
            account=account,
            amount=difference,
            action="adjust",
            note=None,
        )
        account.balance_at = models.today_iso()

    account.updated_at = models.utcnow_iso()
    db.commit()
    db.refresh(account)

    updated = _valued(db, account)
    if outcome.movement is not None:
        updated.cash = cash_report(db, outcome)
    return updated
