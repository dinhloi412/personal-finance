"""Settings: the base currency, the language, and what this build supports.

The supported lists come from the same constants the validators use, so the
frontend can build its dropdowns from the server's answer instead of hard-coding
a list that drifts from what the API accepts.
"""

from __future__ import annotations

from fastapi import APIRouter

from app import models, settings_store
from app.database import DEFAULT_DB_PATH
from app.money import BASE_CURRENCIES, CURRENCIES, LANGUAGES, MARKET_KINDS
from app.routers.deps import DbSession, refused
from app.schemas import SettingsOut, SettingsPatch, WipeOut
from app import __version__

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _current(db) -> SettingsOut:
    return SettingsOut(
        base_currency=settings_store.base_currency(db),
        language=settings_store.language(db),
        cash_linked=settings_store.cash_linked(db),
        supported_currencies=list(CURRENCIES),
        supported_kinds=[*MARKET_KINDS, "cash"],
        supported_languages=list(LANGUAGES),
        database_path=str(DEFAULT_DB_PATH),
        version=__version__,
    )


@router.get("", response_model=SettingsOut)
def read_settings(db: DbSession) -> SettingsOut:
    return _current(db)


@router.patch("", response_model=SettingsOut)
def update_settings(payload: SettingsPatch, db: DbSession) -> SettingsOut:
    """Change the base currency and/or the language.

    Changing the base does not touch recorded history: a valuation keeps the
    base it was written in (see `app.models.Valuation`).
    """
    if payload.base_currency is not None:
        try:
            settings_store.set_base_currency(db, payload.base_currency)
        except settings_store.SettingRefused as cause:
            raise refused(str(cause)) from cause
        # A base with no rate in it cannot convert anything, so make sure one
        # exists — for both bases, since the user can switch straight back.
        from app import fx

        for code in BASE_CURRENCIES:
            fx.seed_rates(db, code)

    if payload.language is not None:
        try:
            settings_store.set_language(db, payload.language)
        except settings_store.SettingRefused as cause:
            raise refused(str(cause)) from cause

    if payload.cash_linked is not None:
        try:
            settings_store.set_cash_linked(db, payload.cash_linked)
        except settings_store.SettingRefused as cause:
            raise refused(str(cause)) from cause

    return _current(db)


@router.post("/wipe", response_model=WipeOut)
def wipe(db: DbSession) -> WipeOut:
    """Delete every record the user has entered.

    The settings and the cached prices and rates are kept: they are not the
    user's data, they are what makes the app work, and throwing away a rate
    would leave a fresh start with nothing to convert with.

    Every table of records is listed here, not only the ones a portfolio is
    mostly made of. A "delete all data" that left the savings accounts, the gold
    and the sales behind would be the worst kind of wipe: the user believes the
    machine is clean, and four of the six things they typed are still on it.

    This exists because a local-first app has no "delete my account" — the
    alternative is the user editing a SQLite file by hand, which is exactly the
    kind of instruction that ends with a lost database.
    """
    # Movements before accounts: deleting an account takes its history with it at
    # the database level, so counting the movements afterwards would always be zero
    # — a wipe report that says it removed nothing is worse than no report.
    removed = {
        "assets": db.query(models.Asset).delete(),
        "realized": db.query(models.Realized).delete(),
        "movements": db.query(models.CashMovement).delete(),
        "cash": db.query(models.CashAccount).delete(),
        "deposits": db.query(models.Deposit).delete(),
        "gold": db.query(models.Gold).delete(),
        "valuations": db.query(models.Valuation).delete(),
    }
    db.commit()
    # Cash is one pot per currency and always exists, so a wipe empties them
    # rather than leaving a portfolio with no cash at all: what was deleted were
    # the balances, not the fact that there is a balance.
    from app import cash

    cash.ensure_pots(db)
    return WipeOut(removed=removed)
