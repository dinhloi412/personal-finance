"""Money moving between cash and a holding, in one place.

When the cash link is on (see `app.settings_store.cash_linked`), a trade is two
facts written together: the holding changed, **and** money left or entered an
account. This module owns the second half of that, and nothing else does —
because the alternative is six endpoints each adjusting a balance slightly
differently, and a balance that disagrees with its own history.

The rules, stated once:

1. **A movement is a signed amount in the account's currency.** Negative is
   money out. The balance is updated by the same number that is written down,
   so the two can never tell different stories.
2. **The pot is chosen by the trade's own currency, not by the user.** A trade
   in dollars moves the dollar pot and a trade in đồng moves the đồng pot, which
   is what "one pot per currency" means and why the common case needs no
   conversion at all — the amount that moves is the amount of the trade. The
   user still states **what actually left the account** when it differs from the
   trade (a fee, a rate the bank applied); a pot of another currency is only
   reached when the trade's own currency has none (an EUR-quoted holding), and
   then today's rate is used and recorded.
3. **Nothing is invented where nothing was paid.** A holding recorded while the
   link was off has no debit behind it, so deleting it gives back nothing —
   `net_invested` is why, and `refund` says so rather than crediting the cost
   basis.
4. **The link never blocks the record.** If there is no usable account, or no
   rate between two currencies, the trade is still written down and this module
   returns *why* the cash side was skipped. An app that refused to record a
   purchase because it could not fill in the cash row would lose the more
   important of the two facts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import cash, fx, models, settings_store
from app.money import FlowAction, SubjectKind


@dataclass(frozen=True)
class Outcome:
    """What a movement did, for the endpoint that asked for it.

    A dataclass rather than a bare row because "nothing moved" is a normal
    answer here, and it travels with the reason why.
    """

    movement: models.CashMovement | None = None
    #: A code the interface turns into words, when there is no flow.
    skipped: str | None = None

    @property
    def moved(self) -> bool:
        return self.movement is not None


#: Why nothing moved. Codes, shared with the UI, never sentences.
SKIP_OFF = "link_off"
SKIP_NO_AMOUNT = "no_amount"
SKIP_NO_ACCOUNT = "no_account"
SKIP_NO_RATE = "no_rate"
SKIP_NOTHING_PAID = "nothing_paid"

#: The codes the API will hand to a client, in one place so the schema's
#: `Literal` and this module cannot drift apart.
SKIP_CODES = (SKIP_OFF, SKIP_NO_AMOUNT, SKIP_NO_ACCOUNT, SKIP_NO_RATE, SKIP_NOTHING_PAID)


def linked(session: Session) -> bool:
    """Whether trades move money at all."""
    return settings_store.cash_linked(session)


def pot_for(session: Session, currency: str) -> models.CashAccount | None:
    """The pot a movement in `currency` belongs to.

    Its own pot first. When there is none — a quote in a currency this app does
    not hold cash in — the primary pot pays, converted, because refusing to move
    the money at all would leave the trade half written. Both pots exist in
    practice (`app.cash` makes sure of it), so this is the exception, not the
    rule.
    """
    account = cash.pot(session, currency) or cash.primary(session)
    if account is None:
        # No pots at all: a wipe emptied the table, or this is the first write
        # on a database that has never been read. Making them here is what keeps
        # "one pot per currency" true rather than merely intended.
        cash.ensure_pots(session)
        account = cash.pot(session, currency) or cash.primary(session)
    return account


def _converted(
    session: Session, amount: float, from_currency: str, to_currency: str
) -> tuple[float, float | None] | None:
    """`amount` in `to_currency`, with the rate used.

    None when the two differ and there is no rate: converting at an invented
    rate would write a made-up number into a balance the user counts. The
    caller turns that into `SKIP_NO_RATE`, and the user can still say what
    actually moved.
    """
    if from_currency.upper() == to_currency.upper():
        return amount, None

    converter = fx.Converter(session=session, base=to_currency.upper())
    converted = converter.to_base(amount, from_currency.upper())
    if converted is None:
        return None
    rate = abs(converted / amount) if amount else None
    return converted, rate


def _write(
    session: Session,
    *,
    amount: float,
    currency: str,
    cash_amount: float | None,
    subject: SubjectKind,
    action: FlowAction,
    name: str,
    account: models.CashAccount | None = None,
    symbol: str | None = None,
    holding_id: int | None = None,
    occurred_on: str | None = None,
    note: str | None = None,
    force: bool = False,
) -> Outcome:
    """Write one movement. `amount` is signed, in the *holding's* currency.

    Everything public below is a sign and a reason on top of this, which is what
    keeps "the balance moved by what the row says" true for all of them.

    `account` is the exception, not the norm: a movement belongs to the pot of
    its own currency, and only a correction or a refund — which must return to
    the money that actually paid — names one.
    """
    if not linked(session) and not force:
        return Outcome(skipped=SKIP_OFF)
    if amount == 0:
        return Outcome(skipped=SKIP_NO_AMOUNT)

    account = account or pot_for(session, currency)
    if account is None:
        return Outcome(skipped=SKIP_NO_ACCOUNT)

    if cash_amount is not None:
        # The user's own figure, in the account's currency. The sign comes from
        # the direction of the movement, not from how they typed it.
        moved = math.copysign(abs(float(cash_amount)), amount)
        rate = (
            None
            if currency.upper() == account.currency.upper() or not amount
            else abs(moved / amount)
        )
    else:
        converted = _converted(session, amount, currency, account.currency)
        if converted is None:
            return Outcome(skipped=SKIP_NO_RATE)
        moved, rate = converted

    if moved == 0:
        return Outcome(skipped=SKIP_NO_AMOUNT)

    movement = models.CashMovement(
        account_id=account.id,
        subject=subject,
        action=action,
        holding_id=holding_id,
        symbol=symbol,
        name=name,
        amount=moved,
        currency=account.currency,
        rate=rate,
        occurred_on=occurred_on or models.today_iso(),
        note=note,
    )
    session.add(movement)

    # The balance and the history are the same number by construction: this line
    # applies exactly what the row above records.
    account.balance = float(account.balance or 0.0) + moved
    account.balance_at = movement.occurred_on
    account.updated_at = models.utcnow_iso()

    session.flush()
    return Outcome(movement=movement)


def spend(
    session: Session,
    *,
    subject: SubjectKind,
    action: FlowAction,
    name: str,
    amount: float | None,
    currency: str,
    cash_amount: float | None = None,
    symbol: str | None = None,
    holding_id: int | None = None,
    occurred_on: str | None = None,
    note: str | None = None,
) -> Outcome:
    """Money leaving an account: a purchase, or the principal of a deposit.

    A holding with no cost recorded has nothing to pay for, so nothing moves.
    """
    if amount is None or amount <= 0:
        return Outcome(skipped=SKIP_NO_AMOUNT)
    return _write(
        session,
        amount=-abs(amount),
        currency=currency,
        cash_amount=cash_amount,
        subject=subject,
        action=action,
        name=name,
        symbol=symbol,
        holding_id=holding_id,
        occurred_on=occurred_on,
        note=note,
    )


def receive(
    session: Session,
    *,
    subject: SubjectKind,
    action: FlowAction,
    name: str,
    amount: float | None,
    currency: str,
    cash_amount: float | None = None,
    symbol: str | None = None,
    holding_id: int | None = None,
    occurred_on: str | None = None,
    note: str | None = None,
    force: bool = False,
) -> Outcome:
    """Money entering the pot: a sale, or a deposit paid out.

    `force` is for the one kind of movement the cash link does not govern: money
    arriving from a closed deposit, which has to land in the pot whether the
    switch is on or off, because there is nowhere else for it to go and no line
    of history to explain it if it arrived silently.
    """
    if amount is None or amount <= 0:
        return Outcome(skipped=SKIP_NO_AMOUNT)
    return _write(
        session,
        amount=abs(amount),
        currency=currency,
        cash_amount=cash_amount,
        subject=subject,
        action=action,
        name=name,
        symbol=symbol,
        holding_id=holding_id,
        occurred_on=occurred_on,
        note=note,
        force=force,
    )


def adjust(
    session: Session,
    *,
    subject: SubjectKind,
    name: str,
    delta: float,
    currency: str,
    symbol: str | None = None,
    holding_id: int | None = None,
    occurred_on: str | None = None,
    note: str | None = None,
) -> Outcome:
    """Only the difference moved: an edited cost basis, or an edited principal.

    `delta` is the change in the holding's own currency, so its sign already
    says which way the money went: a cost basis edited upwards means more was
    paid, which is money out — the same direction as the purchase it corrects.

    The money goes back to **the pot that paid for this holding**: a correction
    belongs to the same money the original movement did, which matters only in
    the corner where the purchase had to fall back to another currency's pot.
    """
    if delta == 0:
        return Outcome(skipped=SKIP_NO_AMOUNT)
    previous = (
        _last_movement(session, subject=subject, holding_id=holding_id)
        if holding_id is not None
        else None
    )
    return _write(
        session,
        amount=-delta,
        currency=currency,
        cash_amount=None,
        subject=subject,
        action="adjust",
        name=name,
        account=(
            session.get(models.CashAccount, previous.account_id) if previous else None
        ),
        symbol=symbol,
        holding_id=holding_id,
        occurred_on=occurred_on,
        note=note,
    )


def entry(
    session: Session,
    *,
    account: models.CashAccount,
    amount: float,
    action: FlowAction,
    occurred_on: str | None = None,
    note: str | None = None,
) -> Outcome:
    """One movement of a balance, with no holding behind it.

    Two things are this: money the user says **entered or left** the balance
    (`in` / `out` — a salary, a bill, a gift), and the correction when they count
    the balance and it is not what the page said (`adjust`). Both are in the
    pot's own currency, so there is nothing to convert, and both go through
    `_write` so the balance and the row are written from one value — which is
    what lets the page claim that a balance is the sum of its history.

    `force` is what makes this work with the cash link off. The link governs
    *trades*; money arriving on the Cash page is the user's own record of their
    own money, and refusing to write it down because a switch is off would make
    the switch mean more than it says.
    """
    if amount == 0:
        return Outcome(skipped=SKIP_NO_AMOUNT)
    return _write(
        session,
        amount=amount,
        currency=account.currency,
        cash_amount=None,
        subject="cash",
        action=action,
        name=account.name,
        account=account,
        occurred_on=occurred_on,
        note=note,
        force=True,
    )


def net_invested(session: Session, *, subject: SubjectKind, holding_id: int) -> float:
    """How much of an account's money a holding still has in it.

    Every movement for the holding, added up as written: purchases are negative,
    sales positive, adjustments whichever way they went. A position bought for
    10 000 000 and half sold for 7 000 000 has 3 000 000 still in it.

    This is what a delete gives back, and it is deliberately **not** the cost
    basis. The cost basis is what the holding is measured against; this is what
    the account paid. After a partial sale the two differ by exactly the gain or
    loss already realised — refunding the cost basis would put money back into
    the account that never left it.
    """
    total = session.execute(
        select(func.coalesce(func.sum(models.CashMovement.amount), 0.0)).where(
            models.CashMovement.subject == subject,
            models.CashMovement.holding_id == holding_id,
        )
    ).scalar_one()
    return float(total or 0.0)


def _last_movement(
    session: Session, *, subject: SubjectKind, holding_id: int
) -> models.CashMovement | None:
    """The most recent movement for a holding — where it last paid from."""
    return session.execute(
        select(models.CashMovement)
        .where(
            models.CashMovement.subject == subject,
            models.CashMovement.holding_id == holding_id,
        )
        .order_by(models.CashMovement.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def refund(
    session: Session,
    *,
    subject: SubjectKind,
    holding_id: int,
    name: str,
    symbol: str | None = None,
    note: str | None = None,
) -> Outcome:
    """Give back what a deleted holding still had in the account it paid from.

    Refuses to invent money: a holding whose purchase never came out of cash —
    recorded before the link was turned on — has nothing to give back, and this
    returns `nothing_paid` rather than a credit. That is also the honest answer
    for a holding that has already returned more than it took, which is what a
    gain on a partial sale looks like.
    """
    if not linked(session):
        return Outcome(skipped=SKIP_OFF)

    still_in = net_invested(session, subject=subject, holding_id=holding_id)
    if still_in >= 0:
        return Outcome(skipped=SKIP_NOTHING_PAID)

    previous = _last_movement(session, subject=subject, holding_id=holding_id)
    # The refund is expressed in the pot's own currency and aimed at the pot
    # that paid, because the money is already sitting there: there is nothing
    # left to convert.
    return _write(
        session,
        amount=-float(still_in),
        currency=previous.currency if previous else cash.PRIMARY_CURRENCY,
        cash_amount=None,
        subject=subject,
        action="refund",
        name=name,
        account=(
            session.get(models.CashAccount, previous.account_id) if previous else None
        ),
        symbol=symbol,
        holding_id=holding_id,
        note=note,
    )


def for_portfolio(session: Session) -> list[dict]:
    """Every movement, newest first — the cash history in one list.

    Newest first for the same reason the sales list is: the row the user just
    caused should be the one they see. `occurred_on` leads the ordering because
    it is the date a person recognises; the id breaks ties within a day in the
    order the movements were actually written.
    """
    rows = session.execute(
        select(models.CashMovement).order_by(
            models.CashMovement.occurred_on.desc(), models.CashMovement.id.desc()
        )
    ).scalars()
    return [
        {
            "id": row.id,
            "account_id": row.account_id,
            "subject": row.subject,
            "action": row.action,
            "holding_id": row.holding_id,
            "symbol": row.symbol,
            "name": row.name,
            "amount": row.amount,
            "currency": row.currency,
            "rate": row.rate,
            "occurred_on": row.occurred_on,
            "note": row.note,
        }
        for row in rows
    ]
