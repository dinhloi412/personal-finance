"""The two choices a user makes that outlive a request: base currency and
language.

Both live in the `settings` table rather than in a module constant or a config
file, for the same reason: the value has to be readable by any process that
opens the database (the API, a script, a test), and it must survive a restart.
A constant would be a setting with extra steps, and would be wrong in silence
in the second process.

Both are validated on the way in against the closed sets in `app.money`. A
`base_currency` of "GBP" or a `language` of "fr" is refused at the door, not
discovered later by a total that quietly equals nothing.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.money import (
    BASE_CURRENCIES,
    DEFAULT_BASE_CURRENCY,
    DEFAULT_LANGUAGE,
    LANGUAGES,
    BaseCurrency,
    Language,
)

BASE_CURRENCY_KEY = "base_currency"
LANGUAGE_KEY = "language"


class SettingRefused(ValueError):
    """A setting was given a value this app cannot honour."""


def _read(session: Session, key: str) -> str | None:
    value = session.execute(
        select(models.Setting.value).where(models.Setting.key == key)
    ).scalar_one_or_none()
    return value if value else None


def _write(session: Session, key: str, value: str) -> None:
    row = session.get(models.Setting, key)
    if row is None:
        session.add(models.Setting(key=key, value=value))
    else:
        row.value = value


def base_currency(session: Session) -> BaseCurrency:
    """The currency every total is expressed in.

    Falls back to the default when unset, and to the default again when the
    stored value is one this build no longer supports — a database written by
    an older version must open, not crash.
    """
    stored = _read(session, BASE_CURRENCY_KEY)
    if stored in BASE_CURRENCIES:
        return stored  # type: ignore[return-value]
    return DEFAULT_BASE_CURRENCY


def set_base_currency(session: Session, value: str) -> BaseCurrency:
    """Change the base. History written in the old base is left alone."""
    code = (value or "").upper()
    if code not in BASE_CURRENCIES:
        raise SettingRefused(
            f"{value!r} is not a supported base currency "
            f"(supported: {', '.join(BASE_CURRENCIES)})"
        )
    _write(session, BASE_CURRENCY_KEY, code)
    session.commit()
    return code  # type: ignore[return-value]


def language(session: Session) -> Language:
    """The language the interface is read in."""
    stored = _read(session, LANGUAGE_KEY)
    if stored in LANGUAGES:
        return stored  # type: ignore[return-value]
    return DEFAULT_LANGUAGE


def set_language(session: Session, value: str) -> Language:
    code = (value or "").lower()
    if code not in LANGUAGES:
        raise SettingRefused(
            f"{value!r} is not a supported language "
            f"(supported: {', '.join(LANGUAGES)})"
        )
    _write(session, LANGUAGE_KEY, code)
    session.commit()
    return code  # type: ignore[return-value]
