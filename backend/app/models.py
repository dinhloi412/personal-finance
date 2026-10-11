"""ORM models for SoTaiSan.

Seven tables, one idea each:

- `instruments`  what a symbol IS (name, kind, listing currency). Identity.
- `assets`       a market position you hold (stocks, funds, crypto).
- `cash_accounts` a manual balance, edited by hand when it moves.
- `price_cache`  the last quote seen per symbol, with the close date it is for.
- `fx_rates`     units of a currency per 1 base, one row per published day.
- `valuations`   a dated record of the whole net worth, in the base of its day.
- `settings`     key/value: base currency, language.

Two rules run through all of it:

1. **No unit-less money.** Every amount column is accompanied by a currency
   column, or is explicitly in the base named by the row that contains it.
2. **A price is dated or it is not a price.** `price_cache` and `fx_rates` both
   carry the day they are for, separate from when they were fetched.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.money import DEFAULT_INTEREST_MODE, GOLD_PRICING_BUY


def utcnow_iso() -> str:
    """ISO 8601 timestamp in UTC, to the second (2026-05-30T13:45:12+00:00)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def today_iso() -> str:
    """The date part of `utcnow_iso` — what `valuations.as_of` and a market
    close date are both written as."""
    return datetime.now(timezone.utc).date().isoformat()


class Setting(Base):
    """Global configuration as key/value pairs (`base_currency`, `language`)."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class Instrument(Base):
    """The identity behind a ticker: `VIC.VN` is Vingroup, in VND, on HOSE.

    Identity only — never a quotation. Keeping the name here means a portfolio
    stays readable the day a feed renames a listing, and keeping the price out
    means the row never has to be invalidated when the market moves.
    """

    __tablename__ = "instruments"

    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)  # MarketKind
    # The listing's trading currency as reported by the feed. Null means "not
    # yet known", which is different from VND and must not be defaulted to it:
    # an unknown currency cannot be converted, and saying it is VND would add
    # dollars to a dong total.
    currency: Mapped[str | None] = mapped_column(String, nullable=True)
    exchange: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[str] = mapped_column(String, default=utcnow_iso, nullable=False)

    assets: Mapped[list["Asset"]] = relationship(back_populates="instrument")


class Asset(Base):
    """One market position: `quantity` of one instrument, bought for
    `cost_basis` (the total paid, in the instrument's currency).

    `cost_basis` is nullable and stays nullable. Deriving a cost from the
    current value is what turns "profit" into "movement since I wrote it down",
    and a tracker that lies about the one number the user cannot recompute is
    worse than one that says "unknown".
    """

    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(
        ForeignKey("instruments.symbol", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String, nullable=False)  # MarketKind
    # Nullable, and refused by the schema rather than by the database: a client
    # that clears the name must get a 422 explaining it, not a 500 from a
    # constraint it could not have known about. The router substitutes the
    # symbol, so in practice nothing is ever stored here as null.
    name: Mapped[str] = mapped_column(String, nullable=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # Total amount paid, in `currency` — not a per-unit price. A per-unit price
    # cannot be averaged across several purchases at different prices.
    cost_basis: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String, nullable=False)  # Currency
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String, default=utcnow_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=utcnow_iso, nullable=False)

    instrument: Mapped["Instrument"] = relationship(back_populates="assets")

    __table_args__ = (Index("ix_assets_kind", "kind"),)


class CashAccount(Base):
    """Cash, in its own table because it is its own kind of thing.

    There is no symbol, no quantity and no price: there is a balance and the
    day it was written down. When the user edits it, that is the whole update.
    """

    __tablename__ = "cash_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)  # Currency
    balance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    balance_at: Mapped[str] = mapped_column(String, default=today_iso, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=utcnow_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=utcnow_iso, nullable=False)


class Deposit(Base):
    """A term deposit: money lent to a bank for a fixed period at a fixed rate.

    Not cash and not a market position, and stored separately for the same
    reason cash is. It has no symbol and no quote — its value is *computed* from
    its own terms — but unlike cash it is not a number the user re-types: the
    principal is fixed at the start and the interest accrues by the day. Asking
    someone to retype a figure the app can derive is asking them to be the
    database.

    What the user does have to supply is what no source knows:

    - `principal` and `currency`: how much, in what.
    - `annual_rate`: the percentage the contract quotes, per year.
    - `start_date`: when the money left, and therefore when interest began.
    - `maturity_date`: when the contract ends. Null is a demand deposit
      (không kỳ hạn), which has no end and keeps accruing.

    The one convention worth stating: interest accrues on ACTUAL days held over
    365, and is not compounded before maturity. That is how a Vietnamese term
    deposit pays, and modelling daily compounding instead would overstate the
    figure the user is about to compare with their bank's.
    """

    __tablename__ = "deposits"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)  # Currency
    principal: Mapped[float] = mapped_column(Float, nullable=False)
    annual_rate: Mapped[float] = mapped_column(Float, nullable=False)  # percent/year
    start_date: Mapped[str] = mapped_column(String, nullable=False)  # YYYY-MM-DD
    #: Null for a demand deposit: no end, so interest never stops accruing.
    maturity_date: Mapped[str | None] = mapped_column(String, nullable=True)
    interest_mode: Mapped[str] = mapped_column(
        String, nullable=False, default=DEFAULT_INTEREST_MODE
    )  # InterestMode
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String, default=utcnow_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=utcnow_iso, nullable=False)

    __table_args__ = (Index("ix_deposits_maturity", "maturity_date"),)


class Gold(Base):
    """A weight of Vietnamese gold, priced by the shop it would be sold to.

    Its own table because it is its own kind of thing: no symbol to quote, no
    issuer, no manager, no NAV. A quantity of metal, the unit it is kept in,
    and a product line at a goldshop whose price it follows.

    The price is not the world price. SJC bars and 9999 rings trade at a
    domestic premium fixed by supply and by the State Bank's import rules, and
    that premium is where most of the money is. So a holding points at a
    product the shop publishes — `vang-mieng-sjc-vang-sjc` — and is valued at
    that product's own price, converted from the shop's unit to the one held.

    `pricing` says which of the shop's two prices to use, and it is a stored
    choice rather than a default buried in code: `buy` is what the shop pays
    you today, `sell` is what it charges. Valuing gold at the sell price shows
    a profit on gold bought a moment ago.
    """

    __tablename__ = "gold"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)  # Currency
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String, nullable=False)  # GoldUnit
    #: The goldshop line this holding follows, as `gold.normalise_key` makes it.
    #: A key rather than a display name, because the shop edits its names.
    product_key: Mapped[str] = mapped_column(String, nullable=False, index=True)
    #: `buy` or `sell` — see the class docstring.
    pricing: Mapped[str] = mapped_column(
        String, nullable=False, default=GOLD_PRICING_BUY
    )
    #: Total paid, in `currency` — the same meaning it has on a position.
    cost_basis: Mapped[float | None] = mapped_column(Float, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String, default=utcnow_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=utcnow_iso, nullable=False)


class PriceCache(Base):
    """The last quote seen for a symbol, and the close it is for.

    Two dates, two jobs: `as_of` is the market session the close belongs to
    (what the number is ABOUT), `fetched_at` is when we last asked (how old the
    asking is). A stale price is still shown — it beats nothing — but always
    with its date attached.
    """

    __tablename__ = "price_cache"

    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    # The listing currency of the quote. Null means the feed did not say, and a
    # price whose currency is unknown is not converted as though it were the
    # base.
    currency: Mapped[str | None] = mapped_column(String, nullable=True)
    as_of: Mapped[str] = mapped_column(String, nullable=False)  # market close date
    fetched_at: Mapped[str] = mapped_column(String, default=utcnow_iso, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Which feed priced it: "market" for a listed price, "fund" for a NAV.
    #: Kept so the next refresh asks the right one first, and so the interface
    #: can say where a number came from — a NAV and a market close are not the
    #: same kind of fact and should not be shown as though they were.
    source: Mapped[str] = mapped_column(
        String, nullable=False, default="market", server_default="market"
    )


class FxRate(Base):
    """Units of `currency` per 1 unit of `base`, as published for `as_of`.

    A row per day, kept rather than overwritten: three readers want a day other
    than today (the history chart, a valuation written last week, the "what
    rate did that total use" panel), and they read it from here.

    `base` is part of the key because a rate is not a number without it. The
    feed never lists its own base among its rates, so rows that did not say
    which base they were fetched against would be read against whichever base
    asked next.
    """

    __tablename__ = "fx_rates"

    base: Mapped[str] = mapped_column(String, primary_key=True)
    currency: Mapped[str] = mapped_column(String, primary_key=True)
    as_of: Mapped[str] = mapped_column(String, primary_key=True)
    rate: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False, default="seed")
    fetched_at: Mapped[str] = mapped_column(String, default=utcnow_iso, nullable=False)

    __table_args__ = (Index("ix_fx_rates_lookup", "base", "currency", "as_of"),)


class Valuation(Base):
    """The whole net worth on one day, as it was computed then.

    Written in the base currency in force at the time, and recording that base
    in `base_currency`. Changing the base later therefore never rewrites
    history: the chart draws each point in the base it was written in and can
    say so, instead of re-expressing old totals at today's rate and calling the
    difference performance.
    """

    __tablename__ = "valuations"

    as_of: Mapped[str] = mapped_column(String, primary_key=True)  # YYYY-MM-DD
    base_currency: Mapped[str] = mapped_column(String, nullable=False)
    total: Mapped[float] = mapped_column(Float, nullable=False)
    market_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cash_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    deposit_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    gold_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # What the parts cost, in the same base, so the chart can show gain over
    # time without re-reading every position's cost basis as it is today.
    cost_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Count of positions excluded from the totals because they could not be
    # converted. A total that is short must say that it is short.
    unconverted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(String, default=utcnow_iso, nullable=False)
