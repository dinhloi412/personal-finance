"""Cash: a name, a currency, a balance, and the day it was written down.

This is the whole feature. There is no ledger, no transaction history and no
reconciliation: when the balance moves, the user types the new number and the
day is stamped. That is deliberate — the user asked for exactly this, and a
ledger nobody maintains is worse than a balance everybody updates.

The only thing worth being careful about is the currency: it is required, it is
VND or USD, and it is never inferred from the name of the bank.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, status
from sqlalchemy import select

from app import fx, models, settings_store, valuation
from app.routers.deps import DbSession, get_or_404
from app.schemas import CashCreate, CashOut, CashUpdate

router = APIRouter(prefix="/api/cash", tags=["cash"])


def _valued(session, account: models.CashAccount) -> CashOut:
    base = settings_store.base_currency(session)
    converter = fx.Converter(session=session, base=base)
    return CashOut.model_validate(valuation.value_cash(account, converter))


@router.get("", response_model=list[CashOut])
def list_cash(
    db: DbSession,
    currency: str | None = Query(default=None, description="VND | USD"),
) -> list[CashOut]:
    statement = select(models.CashAccount).order_by(models.CashAccount.name)
    if currency:
        statement = statement.where(models.CashAccount.currency == currency.upper())
    return [_valued(db, account) for account in db.execute(statement).scalars()]


@router.post("", response_model=CashOut, status_code=status.HTTP_201_CREATED)
def create_cash(payload: CashCreate, db: DbSession) -> CashOut:
    account = models.CashAccount(
        name=payload.name.strip(),
        currency=payload.currency,
        balance=payload.balance,
        note=payload.note,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return _valued(db, account)


@router.get("/{account_id}", response_model=CashOut)
def read_cash(account_id: int, db: DbSession) -> CashOut:
    return _valued(db, get_or_404(db, models.CashAccount, account_id, "Cash account"))


@router.patch("/{account_id}", response_model=CashOut)
def update_cash(account_id: int, payload: CashUpdate, db: DbSession) -> CashOut:
    """Edit a balance — the manual update, in one request.

    `balance_at` is stamped to today whenever the balance itself changes, so
    the page can say how old each figure is. Renaming an account does not
    restamp it: the money did not move.
    """
    account = get_or_404(db, models.CashAccount, account_id, "Cash account")
    fields = payload.model_dump(exclude_unset=True)

    if "name" in fields and fields["name"]:
        fields["name"] = fields["name"].strip()
    balance_changed = "balance" in fields and fields["balance"] != account.balance

    for key, value in fields.items():
        setattr(account, key, value)

    if balance_changed:
        account.balance_at = models.today_iso()
    account.updated_at = models.utcnow_iso()
    db.commit()
    db.refresh(account)
    return _valued(db, account)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cash(account_id: int, db: DbSession) -> None:
    account = get_or_404(db, models.CashAccount, account_id, "Cash account")
    db.delete(account)
    db.commit()
