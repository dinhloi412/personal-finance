"""ORM models for SoTaiSan.

Nine tables, one idea each:

- `instruments`  what a symbol IS (name, kind, listing currency). Identity.
- `assets`       a market position you hold (stocks, funds, crypto).
- `realized`     a market position you SOLD: the trade, kept after the row goes.
- `cash_accounts` the cash balance: one pot per currency, accumulated into.
- `cash_flows`   one movement of that balance, and what caused it.
- `price_cache`  the last quote seen per symbol, with the close date it is for.
- `fx_rates`     units of a currency per 1 base, one row per published day.
- `valuations`   a dated record of the whole net worth, in the base of its day.
- `settings`     key/value: base currency, language, whether cash is linked.

Two rules run through all of it:

1. **No unit-less money.** Every amount column is accompanied by a currency
   column, or is explicitly in the base named by the row that contains it.
2. **A price is dated or it is not a price.** `price_cache` and `fx_rates` both
   carry the day they are for, separate from when they were fetched.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.money import DEFAULT_INTEREST_MODE, GOLD_PRICING_SELL


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


class Realized(Base):
    """One closed market position: what was sold, for how much, and what went.

    A position that has been sold leaves `assets`, and the gain it locked in
    must not leave with it. This table is that record and nothing more. It keeps
    the *facts of the trade* in the currencies they happened in — `cost_removed`
    in the position's own currency, `proceeds` in the market's — and every
    base-currency figure is derived on read, exactly as it is for a live
    position. That is what separates this table from `valuations`: a valuation
    point is a total frozen on a day, while a sale is a holding-shaped fact that
    is still converted the way the rest of the portfolio is.

    Two consequences of that, both deliberate:

    - **No foreign key to `instruments`.** The row has to stay readable after
      the position is gone, so it carries its own `symbol`, `name` and `kind`.
      An FK would make history depend on a registry row that exists for the sake
      of live quotes.
    - **`cost_removed` is proportional** to the part of the position sold — the
      arithmetic is in `app.realized`, and the reason it must be proportional
      rather than exact is that only the position's *total* cost was ever
      recorded. It is nullable for the same reason `assets.cost_basis` is: a
      sale whose cost nobody wrote down is a sale whose gain is unknown, not a
      sale that made a profit.
    """

    __tablename__ = "realized"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String, nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)  # MarketKind
    name: Mapped[str] = mapped_column(String, nullable=False)

    #: Units sold. Always positive — this row records a sale, not a movement.
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    #: The currency `cost_removed` is in: the position's, which is where the
    #: cost was recorded and is not necessarily where the share was quoted.
    currency: Mapped[str] = mapped_column(String, nullable=False)

    #: The part of the position's cost basis that this sale released, in
    #: `currency`. Null when the position never had a cost recorded.
    cost_removed: Mapped[float | None] = mapped_column(Float, nullable=True)
    #: Total received, in `proceeds_currency` — the market's currency for the
    #: symbol, or the position's own when no quote was ever seen.
    proceeds: Mapped[float] = mapped_column(Float, nullable=False)
    proceeds_currency: Mapped[str] = mapped_column(String, nullable=False)

    sold_on: Mapped[str] = mapped_column(String, nullable=False, index=True)  # YYYY-MM-DD
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String, default=utcnow_iso, nullable=False)


class CashAccount(Base):
    """Cash: **one pot per currency**, accumulated into by every trade.

    There is no symbol, no quantity and no price: there is a balance and the day
    it was written down. When the user edits it, that is the whole update —
    which is still true, and still the reason this table exists rather than a
    ledger.

    What it is *not* is a list. A user has a bank balance in đồng and sometimes
    one in dollars, not five piles of money to choose between, so there is one
    row per currency and the currency is its identity: `UniqueConstraint` says
    so, and `app.cash` is what makes it true (creating the two pots, and merging
    the duplicates an older database may still hold).
    """

    __tablename__ = "cash_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    #: A label for the pot — `VND`, `USD`, or whatever the user calls that
    #: balance. It is never the thing that identifies it: the currency is.
    name: Mapped[str] = mapped_column(String, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)  # Currency
    balance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    balance_at: Mapped[str] = mapped_column(String, default=today_iso, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=utcnow_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=utcnow_iso, nullable=False)

    #: One pot per currency. Enforced by the database on a schema built from
    #: these models; a database written before this constraint existed cannot
    #: gain one (SQLite does not alter constraints), which is why `app.cash`
    #: also enforces it — and merges what is already there.
    __table_args__ = (UniqueConstraint("currency", name="uq_cash_accounts_currency"),)


class CashMovement(Base):
    """One movement of a cash balance, and what caused it.

    Cash is still a balance the user counts — this table does not replace that,
    and editing the balance by hand stays the whole update. What it adds is the
    answer to a question the balance alone cannot answer: **where did it go, and
    why**. Once trades can move money (see `app.movements`), a balance that
    changed on its own would be a number with no story behind it.

    Three things about the shape:

    - **The amount is signed.** Negative is money leaving the account. A pair of
      unsigned columns (`debit`/`credit`) would make every sum a decision about
      which one to subtract, and the running balance on the page is a sum.
    - **No foreign key to the holding.** The flow has to stay readable after the
      position is deleted — that is exactly when the user wants to know what
      happened — so it carries its own `symbol`/`name` snapshot, like
      `Realized`. The account IS a foreign key, because a movement without an
      account is not a movement; deleting an account takes its history with it.
    - **`rate` is recorded when one was used.** A dollar purchase paid from a
      dong account used a rate; keeping it makes the row reproducible, and
      leaving it null says plainly that the two amounts were the same currency
      and no rate was involved.
    """

    __tablename__ = "cash_movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("cash_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )

    #: What caused it: `asset` | `gold` | `deposit`, and which action.
    subject: Mapped[str] = mapped_column(String, nullable=False)  # SubjectKind
    action: Mapped[str] = mapped_column(String, nullable=False)  # FlowAction
    #: The holding's id at the time. Null once the holding is gone; the flow is
    #: history, not a pointer.
    holding_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    #: Snapshotted, so a deleted position still reads as something.
    symbol: Mapped[str | None] = mapped_column(String, nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)

    #: Signed, in `currency`: negative is money out of the account.
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    #: Units of `currency` per 1 unit of the holding's currency, when the two
    #: differed. Null when no conversion was needed.
    rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    occurred_on: Mapped[str] = mapped_column(String, nullable=False, index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String, default=utcnow_iso, nullable=False)

    __table_args__ = (Index("ix_cash_movements_subject", "subject", "holding_id"),)


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
    choice rather than a default buried in code. `sell` — the default — is what
    the shop charges, which is the figure the news quotes and the same basis as
    every other holding here. `buy` is what the shop would pay you today.
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
    #: `sell` or `buy` — see the class docstring. Defaults to what the shop
    #: charges, which is the figure everyone calls "the gold price".
    #:
    #: `server_default` as well as `default`, and that is not belt-and-braces:
    #: a Python-side default is applied by the ORM, so a write that does not go
    #: through the ORM — raw SQL, a migration, another tool — would fall back
    #: to the column's own default. Two declarations of one default is two
    #: chances for them to disagree, and they did: the schema said `buy` while
    #: the model said `sell`, and a holding created without naming its pricing
    #: came out on the wrong side of the spread.
    pricing: Mapped[str] = mapped_column(
        String, nullable=False, default=GOLD_PRICING_SELL, server_default=GOLD_PRICING_SELL
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
