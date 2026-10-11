"""The cash balance: **one pot per currency**, and nothing else.

Cash used to be a list of accounts the user named and added to — Vietcombank,
Techcombank, a new one per matured deposit. That list is what this module
replaces, and the reason is the same one that makes a balance worth keeping: a
user does not have five piles of money, they have a bank balance in đồng and
sometimes one in dollars. Splitting it into rows meant choosing which pile a
purchase came out of, and every extra row was another chance for the money to be
in the wrong one.

So there are exactly two pots — VND and USD — created when the app first looks,
never added to, never deleted, and never re-denominated. They are the input and
the output of every trade (`app.movements`), and money accumulates in them.

**Why two and not one.** This app holds two currencies and can add neither to
the other. One pot would have to be denominated in something, and a dollar
purchase from a dong pot is a conversion the user did at a counter, not
arithmetic the app should assume. Two pots keep every trade in its own currency,
which is also what removes the need to convert anything in the common case.

**A balance is the sum of its history.** Every change to a pot writes a line —
a trade through `app.movements`, or money the user puts in and takes out on the
Cash page. Money that was in the pot before there were lines (`reconcile`, run
at startup) gets one line of its own rather than a silent opening figure, so the
page can say what it says and be right.

**Merging what is already there.** A database written by an earlier version may
hold several accounts in one currency (`data.db` from before this change, or the
demo). They are merged into one — balances summed, the movement history moved
across rather than cascaded away — and the merge is *not* silent: a copy of the
database file is written first, next to it, and the merge is logged. That copy
is the rule this repository set for itself: a migration needs a copy of the file
first, because the alternative is a user's only record being rewritten by a
startup routine they never agreed to.
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.money import BASE_CURRENCIES

logger = logging.getLogger(__name__)

#: The pot that pays when a trade's own currency has no pot — an EUR-quoted
#: holding, say. Đồng is this app's home currency (see `DEFAULT_BASE_CURRENCY`),
#: and it is what a Vietnamese account actually pays out.
PRIMARY_CURRENCY = BASE_CURRENCIES[0]


def pots(session: Session) -> list[models.CashAccount]:
    """Every pot, in the fixed order VND then USD.

    Ordered rather than sorted by name: the list is a pair of balances a person
    reads top to bottom, and it should not rearrange itself when one is renamed.
    """
    rows = list(session.execute(select(models.CashAccount)).scalars())
    order = {code: index for index, code in enumerate(BASE_CURRENCIES)}
    return sorted(rows, key=lambda row: (order.get(row.currency, 99), row.id))


def pot(session: Session, currency: str) -> models.CashAccount | None:
    """The pot for `currency`, or None when the app has not made it yet."""
    code = (currency or "").upper()
    return session.execute(
        select(models.CashAccount).where(models.CashAccount.currency == code)
    ).scalars().first()


def primary(session: Session) -> models.CashAccount | None:
    """The pot that stands in for every other: đồng, or whatever exists."""
    return pot(session, PRIMARY_CURRENCY) or next(iter(pots(session)), None)


def ensure_pots(session: Session) -> list[str]:
    """Make sure both pots exist. Returns the currencies it created.

    Called at startup and again whenever the balances are read, so "there is one
    pot per currency" is a property of the API rather than of the app having
    been started in the right order. Idempotent, and cheap: a wipe empties the
    table, and the next look puts the two empty pots back.
    """
    created: list[str] = []
    for code in BASE_CURRENCIES:
        if pot(session, code) is None:
            session.add(
                models.CashAccount(
                    name=code,
                    currency=code,
                    balance=0.0,
                )
            )
            created.append(code)
    if created:
        session.commit()
    return created


def balance_from_history(session: Session, account: models.CashAccount) -> float:
    """What this pot's own movements add up to."""
    total = session.execute(
        select(func.coalesce(func.sum(models.CashMovement.amount), 0.0)).where(
            models.CashMovement.account_id == account.id
        )
    ).scalar_one()
    return float(total or 0.0)


def reconcile(session: Session, *, source: Path | None = None) -> list[str]:
    """Write a line for money that was in a pot before the history existed.

    The page tells the user that a balance is the sum of the lines below it, and
    that has to be true — including for money typed in before there were any
    lines at all, which is the normal state of a portfolio that existed before
    this feature did. So the difference is written down once, as `adjust`, dated
    the day the balance itself was last counted.

    It runs at startup, next to the merge, and it is idempotent: after the first
    pass the two figures agree, so the second pass writes nothing. A pot that
    has never held money gets no line at all — an empty balance is not a fact
    that needs explaining.
    """
    written: list[str] = []

    for account in pots(session):
        balance = float(account.balance or 0.0)
        if balance == 0.0:
            continue
        difference = balance - balance_from_history(session, account)
        if difference == 0.0:
            continue

        session.add(
            models.CashMovement(
                account_id=account.id,
                subject="cash",
                action="adjust",
                holding_id=None,
                symbol=None,
                name=account.name,
                amount=difference,
                currency=account.currency,
                rate=None,
                occurred_on=account.balance_at or models.today_iso(),
                note=None,
            )
        )
        written.append(f"{account.currency}: {difference:+g}")

    if written:
        if source is not None:
            copy_database(source)
        session.commit()
        for line in written:
            logger.warning(
                "recorded a cash balance that had no history behind it — %s", line
            )

    return written


def backup_path(target: Path) -> Path:
    """Where a pre-merge copy of `target` goes, without clobbering an older one."""
    stamp = models.utcnow_iso().replace(":", "").replace("-", "")[:15]
    return target.with_name(f"{target.name}.before-merge-{stamp}.bak")


def copy_database(source: Path) -> Path | None:
    """A consistent copy of the SQLite file, WAL included.

    `sqlite3`'s own backup API rather than `shutil.copy`: the database runs in
    WAL mode, so a file-level copy can miss the newest commits — and the newest
    commits are exactly what a merge is about to rewrite.
    """
    if not source.is_file():
        return None
    destination = backup_path(source)
    try:
        with sqlite3.connect(source) as origin, sqlite3.connect(destination) as copy:
            origin.backup(copy)
    except sqlite3.Error as cause:  # pragma: no cover - a filesystem problem
        logger.warning("could not write a backup before merging: %s", cause)
        return None
    return destination


def merge_duplicates(session: Session, *, source: Path | None = None) -> list[str]:
    """Fold several accounts of one currency into one. Returns what it merged.

    The first account of a currency is the survivor — lowest id, so it is the
    one the user created first and the one a movement is most likely to point
    at. The others:

    - their balances are **added** to the survivor, which is the whole point:
      the money does not disappear, it stops being in two places;
    - their movements are **re-pointed** to the survivor, not deleted. Deleting
      an account cascades to its history (`models.CashMovement`), and a merge
      that quietly erased half the cash history would be worse than the
      duplication it was fixing;
    - their names are kept in the log, because a name is how the user recognises
      what went where.

    A copy of `source` is written before anything is touched, when `source` is a
    real file. In-memory test databases have nothing to back up.
    """
    merged: list[str] = []

    for code in BASE_CURRENCIES:
        rows = sorted(
            session.execute(
                select(models.CashAccount).where(models.CashAccount.currency == code)
            ).scalars(),
            key=lambda row: row.id,
        )
        if len(rows) < 2:
            continue

        keeper, extras = rows[0], rows[1:]
        keeper.balance = float(keeper.balance or 0.0) + sum(
            float(row.balance or 0.0) for row in extras
        )
        for row in extras:
            session.execute(
                models.CashMovement.__table__.update()
                .where(models.CashMovement.account_id == row.id)
                .values(account_id=keeper.id)
            )
            session.delete(row)
        merged.append(
            f"{code}: " + ", ".join(f"{row.name} ({row.balance:g})" for row in extras)
            + f" → {keeper.name} ({keeper.balance:g})"
        )

    if merged:
        if source is not None:
            copy_database(source)
        session.commit()
        for line in merged:
            logger.warning("merged duplicate cash accounts into one pot — %s", line)

    return merged
