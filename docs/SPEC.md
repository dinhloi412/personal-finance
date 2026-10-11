# SoTaiSan — Đặc tả / Specification

A minimal, self-hosted personal **asset tracker**. Clone-inspired by
[aurelio-finance](https://github.com/LosaLosSantos/aurelio-finance) but reduced
to one job: **keep track of what you own and what it is worth.**

---

## 1. Scope

### 1.1 In scope

| # | Capability |
|---|---|
| 1 | Track **5 asset kinds**: `stock`, `fund` (ETF / mutual fund), `crypto`, `cash`, `deposit` (term savings) |
| 2 | Market assets (`stock`, `fund`, `crypto`) priced automatically from Yahoo Finance |
| 3 | `cash` is a **manual balance** the user edits by hand when it moves |
| 2b | Open-ended Vietnamese funds (quỹ mở) priced by **NAV from Fmarket**, the kind of fund Yahoo cannot price |
| 3b | `deposit` is a **term deposit**: a principal, a rate and a term, whose interest is **computed** day by day |
| 3c | `gold` is a **weight of Vietnamese gold**: a quantity, a unit, and a goldshop product line whose **published price** it follows |
| 4 | **2 currencies**: `VND`, `USD` — one is the *base* for all totals |
| 5 | **2 languages**: `vi` (Tiếng Việt), `en` (English) |
| 6 | Net-worth snapshot history + allocation breakdown |
| 6b | **Sell a position** (part or all): the cost it released is worked out in proportion, and the gain is **kept** as a realised figure after the position is gone |
| 6c | **One cash balance per currency** (VND and USD), with the history of what moved it. There is no "add an account", no naming to choose between, and no delete |
| 6d | **Cash-linked trades** (a switch, off by default): buying, selling, opening and maturing a deposit, and deleting a holding move money in or out of the balance in that trade's own currency, each leaving one signed line of history |
| 7 | Everything local: SQLite file on disk, no account, no cloud |

### 1.2 Explicitly **out of scope**

- ❌ Interest payment schedules other than "at maturity"
- ❌ Goals / targets / planning of any kind
- ❌ AI advisor, chat, agents, MCP server, OpenRouter, web search
- ❌ Income, expenses, budgets, cash-flow analysis
- ❌ Debts, liabilities, mortgages, real assets, insurance, pensions
- ❌ Accumulation plans (PAC), recurring buys, dividend catch-up engine
- ❌ A transaction **ledger**: the *buys* behind a position are not recorded,
  only what it cost in total, so a partial sale releases a proportional share of
  that cost rather than a lot-identified one. A sale is recorded; a purchase
  history is not. Cash movements (§2.4c) record what a *balance* did, not a
  categorised book of account.
- ❌ Cash-flow **analysis**: movements are never categorised, budgeted, summed
  by month or reported on. The module that moves money is called
  `app/movements.py`, and `test_scope.py` refuses one named `cashflow`.
- ❌ Look-through composition (what a fund holds)
- ❌ Multi-user, auth, sync, tax reporting, broker import
- ❌ Currencies other than VND and USD

The removed surface is roughly 25 k lines of Python and 12 k lines of TSX in
the reference project. This spec keeps the three ideas that were worth keeping:
**an instrument registry → dated price cache**, **a base currency with a rule
for converting into it**, and **a net worth that is the sum of its parts.**

---

## 2. Domain model

```
Instrument (symbol registry)      Asset (a position you hold)
  symbol  PK  "AAPL"                id           PK
  name        "Apple Inc."          kind         stock | fund | crypto | cash
  kind        stock|fund|crypto     symbol       FK-ish -> Instrument.symbol (market kinds)
  currency    USD                   name
  exchange                          quantity     float
                                    cost_basis   float | null   (total paid, in `currency`)
PriceCache (last known quote)       currency     VND | USD
  symbol  PK                        note         free text
  price                             created_at / updated_at
  currency  (listing currency)
  as_of     (market close date)   CashAccount (kind = manual, its own table)
  fetched_at                        id           PK
                                    name         "Vietcombank"
FxRate (units of `currency` per 1 BASE)   currency  VND | USD
  base      PK  USD | VND           balance      float
  currency  PK  VND | USD           note
  as_of     PK  YYYY-MM-DD          updated_at
  rate
  fetched_at                      Valuation (daily net-worth record)
                                    as_of  PK  YYYY-MM-DD
Setting (key/value)                 base_currency
  base_currency   VND | USD         total
  language        vi | en           invest_value / cash_value
  cash_linked     true | false      rates_json (currencies used + rates)

CashMovement (one movement of a balance, and what caused it)
  id                 PK
  account_id         FK -> cash_accounts.id, ON DELETE CASCADE
  subject            asset | gold | deposit     (what caused it)
  action             buy | sell | open | close | adjust | refund
  holding_id         the holding's id AT THE TIME; null once it is gone
  symbol / name      snapshotted, so a deleted position still reads as something
  amount             SIGNED, in `currency`: negative is money out of the account
  currency           the account's currency
  rate               units of `currency` per 1 of the holding's; null when equal
  occurred_on        YYYY-MM-DD
  note / created_at

Realized (a position that was SOLD; keeps its own copy)
  id                 PK
  symbol / kind / name      snapshotted: no FK, so the row outlives the position
  quantity                  units sold
  currency                  the position's cost currency
  cost_removed     float | null   proportional part of cost_basis released
  proceeds                  total received
  proceeds_currency         the market's currency for the symbol
  sold_on           YYYY-MM-DD
  note
  created_at
```

### 2.1 Why cash is its own table

Cash has no quantity, no symbol, no price and no cost basis. Forcing it into
`Asset` would mean five nullable columns and a permanent `if kind == "cash"`
branch in every read. It is a balance with a name. It gets a table.

### 2.2 Why a term deposit is its own kind

A term deposit is the third *source of value*, and it is different from both of
the others in the direction that matters:

| | where the value comes from | who decides it |
|---|---|---|
| market position | a quote from outside | the market |
| cash | a balance the user counted | the user |
| **term deposit** | **the agreement: principal, rate, days held** | **the contract** |

So it gets its own table and its own arithmetic (`app/deposits.py`), and it is
*not* folded into cash. Putting it in cash would mean either asking the user to
retype a figure the app can derive from terms it already knows — making them be
the database — or storing only the principal and losing the interest, which is
the entire reason to track a deposit.

Making it a market position would be worse still: it has no symbol to quote and
no cost basis to compare against, so it would arrive with three permanent null
columns and a price feed that can never answer.

### 2.2b Why a deposit has two values, not one

"Value today" (principal + interest accrued so far) and "value at maturity"
(principal + full-term interest) are both shown, because each answers a
different question and either alone is misleading: the first is what the money
is worth now, the second is what it is for. A record that showed only the first
would hide the reason for holding a deposit; only the second would claim money
that has not been earned.

### 2.3 Why an Instrument registry

A symbol is not a name. `VIC.VN` is "Vingroup", `BTC-USD` is "Bitcoin". Storing
the name beside the symbol means the day Yahoo renames a listing the user's
portfolio does not become a wall of tickers. The registry is *identity only* —
it never holds a price (that is `PriceCache`, which is dated and therefore
disposable).

### 2.4 Money arithmetic

- Every stored amount carries the currency it is in. There is no unit-less
  number anywhere in the schema.
- A `Valuation` is written **in the base currency that was in force when it was
  written** and records that base in `rates_json`. Changing the base currency
  later never rewrites history, and the chart says which base each point used.
- Floats, not Decimal: this is a tracker, not a ledger. Amounts are rounded for
  display only.

### 2.4b Why a sale is kept, and what "cost" means when one happens

Selling is the only action in this app that **destroys a figure it cannot
recompute**: a position's `cost_basis`. Delete a position by mistake and the
mistake is visible; sell it and the cost is gone, taking the gain with it. A
tracker that quietly loses the loss on a position you just closed is worse than
one that never tracked it, because the page would then be telling a story about
a portfolio that did better than it did. So `Realized` exists, and `DELETE
/api/assets/{id}` is not how a sale is meant to be recorded.

Two rules make it work:

1. **The cost released is proportional.** A position stores one total
   (`cost_basis`), not the purchases behind it, so selling a third of the
   quantity releases a third of the cost. This is average cost, it is a
   computation rather than a stored fact, and it lives in `app/realized.py`.
   Recording lots instead would be a ledger — see §1.2.
2. **A sale is a fact, not a total.** The row keeps the two amounts in the
   currencies they happened in — `cost_removed` in the position's currency,
   `proceeds` in the market's — and every base-currency figure is derived on
   read, exactly as it is for a live position. `Valuation` freezes a total on a
   day; a sale is converted like the rest of the portfolio, so switching the
   base re-expresses it instead of leaving dong in a dollar table.

**The invariant that proves it works:** selling at the price the market is
quoting must leave the portfolio's *total* gain unchanged — the same money,
moved from unrealised to realised. If it changes, a figure has been invented or
lost. It is asserted in `backend/tests/test_realized.py` and checked against a
running server in `scripts/acceptance.sh`.

Two consequences the UI states plainly:

- **Nothing is posted to cash.** Money that arrived is a balance the user
  counts (§2.1). Inventing a cash row from a sale would put money somewhere they
  never said it went.
- **A fully sold position is deleted, not kept at zero.** A zero-quantity row
  has no value, so it would appear in `unconverted` telling the user that a
  position they have already sold is "not counted" — a warning about nothing.
  The record of the sale is the `Realized` row.

**An unconvertible quote does not block a sale.** `VWCE.DE` is quoted in EUR,
which this app cannot convert, and holding one is allowed (§4) — the price is
reported and left out of the total. Its sale is recorded the same way: the
proceeds are kept in EUR, `proceeds_base` is `None`, `reason` is
`not_convertible`. Refusing would leave the user holding a position they no
longer own, and this app's rule is to report what it cannot convert, not to
refuse the fact.

### 2.4c Why cash is one balance per currency

Cash used to be a list of accounts the user named and added to, and the list was
the problem: it meant choosing which pile a purchase came out of, and every extra
row was another chance for the money to be in the wrong one. A person does not
have five piles of money; they have a bank balance in đồng and sometimes one in
dollars. So there are exactly two rows, `UNIQUE(currency)` says so, and
`app/cash.py` makes it true:

- **they exist before anything asks**: created at startup and again on any read
  of `/api/cash`, so a balance is never missing rather than empty;
- **they cannot be added or removed**: there is no `POST /api/cash` and no
  `DELETE /api/cash/{id}` at all, which is a stronger refusal than a validator
  rejecting a currency. `PATCH` edits the balance, the label and the note;
- **a pot's currency is not editable**: it is the pot's identity, and there are
  two of them.

**A balance is the sum of the lines under it**, and the page says so. Every
change writes one:

| how the money moved | the line |
|---|---|
| a trade — buying, selling, a deposit, gold | `subject` = that holding, through `app.movements` |
| money the user put in or took out themselves | `subject: cash`, `action: in` / `out`, via `POST /api/cash/{id}/entry` |
| the user counted their money and it was a different number | `subject: cash`, `action: adjust`, written by `PATCH /api/cash/{id}` |
| money that was in the pot before there were lines | one opening `adjust`, written by `reconcile` at startup |

The last row is what makes the claim true for a portfolio that existed before
this feature did: rather than a silent opening figure, the difference is written
down once, dated the day the balance was last counted. `reconcile` is
idempotent — after the first pass the two agree and it writes nothing — and a
pot that has never held money gets no line at all.

**Money in and out is not income and expense tracking.** It is one signed amount
and a free-text reason ("Lương tháng 10", "Tiền nhà"): there is no category, no
month, no total by type, and `test_scope.py` refuses a module named after any of
them. The direction is a word rather than a sign in the request, because a form
that asks for "-500000" to mean a withdrawal is a form that will one day record
one the wrong way round.

**Why two and not one.** One pot would have to be denominated in something, and
a dollar purchase paid from a dong pot is a conversion the user did at a counter,
not arithmetic the app should assume. Two pots keep every trade in its own
currency — which is also why the common case needs no rate at all.

**A database from before this rule is merged, not refused.** `merge_cash_pots`
runs at startup (`app/database.py`), adds the duplicate balances together, moves
their movement history onto the surviving account rather than letting it cascade
away, **writes a copy of the database file beside it first**, and logs what it
did. The rule this repository set for itself — a migration needs a copy of the
file first — is kept, and the copy is the answer to "what did it do to my
records".

### 2.4d Why cash can be linked to trades, and why it is off by default

A portfolio is entered twice over: first the holdings, then the balance. During
that pass the two are independent facts — the shares were bought years ago, out
of money that is not the number being typed today — so the link starts **off**,
and turning it on says "from here, trades move money". Nothing is applied
retroactively; a holding recorded while it was off has no debit behind it, which
is exactly what makes deleting it give nothing back (§2.4d).

With it on, one trade writes two facts in one request: the holding changed, and
money entered or left an account. Four rules keep that honest:

1. **A movement is signed and written in the pot's currency**, and the balance
   is updated by the same number the row records. The balance and its history
   cannot tell different stories because they are written from one value.
2. **The pot is the trade's own currency, and the user never chooses it.** A
   trade in dollars moves the dollar pot; a trade in đồng moves the dong pot. In
   the common case that means the amount is the trade's own number to the last
   decimal, with no rate and no rounding. The user can still state **what
   actually left the bank** when it differs — a fee, or a rate they were given.
3. **A currency with no pot falls back to đồng, and says so.** `VWCE.DE` is
   quoted in EUR, which this app neither holds cash in nor converts: the sale is
   recorded, the cash side reports `no_rate`, and no figure is invented to reach
   the dong pot.
4. **Edits move the difference, not the whole figure**, and go back to the pot
   that paid: a corrected cost basis is the same money the purchase was. Clearing
   a cost basis moves nothing — the user has said they no longer know what it
   cost, not that they were refunded.
5. **The link never blocks the record.** No pot, or no rate, and the trade is
   still written; the response says which of the two stopped the cash side. An
   app that refused to record a purchase because it could not fill in the cash
   row would lose the more important half of the transaction.
6. **One movement ignores the switch**: money arriving from a closed deposit.
   With the link off the balance still has to change, and there is nowhere else
   for it to go — so it lands in the pot of the deposit's currency with a line
   saying why, rather than appearing silently.

**A delete gives back what the account paid, not the cost basis** (§2.4e).
Bought for 10 000 000 and half sold for 7 000 000, a position has 3 000 000 of
the account's money left in it, while its remaining cost basis is 5 000 000. The
difference is the gain already realised, and refunding the cost basis would put
money into the account that never left it.

### 2.4e `net_invested`: the figure a delete refunds

```
net_invested(holding) = Σ amounts of that holding's movements   (signed)
refund                = −net_invested      when it is negative
                      = nothing            otherwise
```

The sum is negative when the account is still down on the trade — the ordinary
case — and that is what comes back. It is zero for a holding that was never paid
for out of cash, and it is **positive** for one whose partial sale already
returned more than it took; both give nothing back, and the response says
`nothing_paid` rather than crediting a figure that would be invented.

---

## 3. Currencies and conversion

- Supported: `VND`, `USD`. Enforced at the schema layer (`Literal["VND","USD"]`).
- Base currency lives in `settings.base_currency`, default `VND`.
- Rates are fetched from <https://open.er-api.com/v6/latest/USD> (no key), one
  request per refresh, and flattened into rows of *units of CUR per 1 base*.
- A VND/USD rate is also computable locally from a `USD`-quoted base, so the
  app never needs a second endpoint.
- **Fallback chain** for `as_of` = the day asked for, then the newest older row,
  then the hard-coded seed (`USD→VND = 25 000`) marked `stale`. A stale rate is
  shown with a warning; it is never silently used as if fresh.
- An amount in a currency with no rate converts to `None`, and the UI shows the
  amount "not converted" instead of adding it to a total in the wrong unit.

---

## 4. Pricing

Two sources, because there are two kinds of thing to price and they are priced
by different facts:

| kind | source | the number | published |
|---|---|---|---|
| listed (`stock`, `fund` ETF, `crypto`) | Yahoo Finance | last **close** of a session | per session |
| open-ended `fund` | Fmarket | **NAV** per certificate | once a day |
| `gold` | Bảo Tín Minh Châu | **mua / bán** per product line | a few times a day |

The order is: the source that priced the symbol last time, then the other one,
then a recorded failure. A fund certificate is not listed, so Yahoo will never
price it; a stock has no NAV, so Fmarket never will. Every stored quote carries
`source` (`market` or `fund`) and the interface shows which — a NAV and a close
are not the same kind of fact and must not be displayed as though they were.

### 4.1 Yahoo Finance (listed things)

- The most recent **close** from a short history window is used; Yahoo's
  realtime quote endpoint is unreliable.
- Symbol conventions: `AAPL` (US), `VIC.VN` (HOSE), `VWCE.DE` (Xetra),
  `BTC-USD` / `BTC-EUR` (crypto pairs), `EUNL.DE` (ETF).
- Quotes are cached in `PriceCache` with `as_of` (the close date) and
  `fetched_at`, both always shown so staleness is visible.
- A refresh is **explicit** (button) or on demand when a position has never
  been priced. Failure of one symbol never fails the request: the response
  reports `priced` / `failed` per symbol, and the cached value keeps serving.
- If the quote's currency is neither VND nor USD, the position is reported but
  **not converted**, with an explicit "unsupported currency" flag — the same
  honesty rule as an unknown FX rate.

### 4.2 Fmarket (open-ended funds)

An open-ended fund has no ticker and no session: it has a NAV, published once a
day by the fund's management company. The source is
<https://fmarket.vn>'s public JSON API — no key, structured, and it carries the
day the NAV belongs to. Dragon Capital publishes the same numbers on its own
site, but as an HTML table, and a scraper for a page nobody promised to keep is
a maintenance cost this does not need to pay.

**One fund, several names.** Fmarket uses the fund company's internal code for
Dragon Capital's funds; the certificate and the fund's own website use another.
Both are correct: `DCDE` and `VFMVF4` are the same fund, and their NAVs matched
to the dong when cross-checked against Dragon Capital's published price list.
`backend/app/funds.py::ALIASES` maps one to the other, and a test fails if a
mapped code stops resolving.

- **NAV is a daily figure**, so one request per fund per day is the entire
  budget. A chosen fund is priced from its own endpoint; the catalogue of funds
  is fetched at most once per six hours, and only when someone is searching.
- **There is no NAV history endpoint.** A fund's value is always current NAV;
  a dated valuation of a fund cannot be reconstructed from this source, which
  the price cache's `as_of` makes visible rather than silent.

---

## 5. Valuation

```
market position value_in_listing_ccy = quantity × price
value_in_base = convert(value, price_currency → base)
cost_in_base  = convert(cost_basis, asset_currency → base)
gain          = value_in_base − cost_in_base        (null if cost is null)
cash value    = convert(balance, cash currency → base)

term deposit  interest = principal × annual_rate/100 × days_held / 365
              value    = principal + interest
              value_in_base = convert(value, deposit currency → base)
total         = Σ market values + Σ cash values + Σ deposit values

closed position (Realized)
  cost_removed  = cost_basis × quantity_sold / quantity_held   (the whole
                  cost_basis when the position is sold in full, so the number
                  the user typed leaves unchanged; null when there was none)
  proceeds_base = convert(proceeds, proceeds_currency → base)
  cost_base     = convert(cost_removed, asset_currency → base)
  gain          = proceeds_base − cost_base
  realized_gain = Σ gains over every sale   (null if ANY sale has no cost)
  total_gain    = gain + realized_gain      (null if either side is unknown)
  total_gain_%  = total_gain / (cost_base + realized_cost_base) × 100
```

- `total` is the sum of conversions, never a sum across mixed units.
- Any position that could not be converted is excluded from `total` and listed
  in `unconverted[]` so the number is never quietly short.
- The same rule governs the realised figures: **one sale whose gain cannot be
  worked out makes `realized_gain` and `total_gain` null rather than too large.**
  There are two ways that happens, and `reason` on the row says which: a cost
  that was never recorded, and proceeds in a currency this app cannot convert
  (a EUR listing, held legally — §4). In both cases the row still shows whatever
  is known. A sale with no cost basis can never be recomputed later, because the
  row it would have been read from is gone; so the figure that would count the
  whole proceeds as profit is not printed.
- A portfolio with no open position has an unrealised gain of 0 rather than an
  unknown one: the only reason `gain` is null there is that there is nothing to
  be wrong about. Without that, selling everything — the exact state this
  feature creates — would answer the one question the user came to ask with
  "not available".

---

### 5.1 The deposit conventions, stated

Three choices, each of which a reader could reasonably have made differently,
and each of which changes the number the user compares with their bank:

1. **Simple interest on actual days over a 365-day year.** A Vietnamese term
   deposit quotes a year rate and pays `principal × rate × days/365` at
   maturity. Daily compounding would overstate every figure by roughly 1.4 %
   and would not match the statement.
2. **Interest stops at maturity.** After the maturity date the money is not
   earning the contract rate any more; it is a new agreement waiting to be
   made. Carrying the old rate forward would invent income, so the value
   freezes at the contractual payout and the record is marked `matured`.
3. **A demand deposit never matures.** `maturity_date = null` means không kỳ
   hạn: interest keeps accruing, and the value keeps rising with nobody doing
   anything. This is the one holding in the app whose value grows on its own.

**Roll-over keeps the interest and the term length.** Rolling a matured deposit
into a new term adds the interest to the principal (what the bank does, and
what would otherwise silently vanish from the portfolio) and gives the new term
the *same number of days* as the one that ended — not the same calendar dates,
which would quietly shorten a term taken across a month of different length.

**Withdrawal moves the money in one request.** Closing a deposit and recording
the proceeds as cash happen together, because doing it in two screens is how a
portfolio ends up holding the same million twice.

### 4.3 Bảo Tín Minh Châu (Vietnamese gold)

Vietnam's gold price is not the world price. SJC bars and 9999 rings carry a
domestic premium fixed by supply and by the State Bank's import rules, and that
premium is where the money is — so this app reads a Vietnamese shop, not a world
feed, from a public JSON endpoint that needs no key.

Four facts about that payload, all found by looking at it:

- **The price is per unit, and the unit is written only inside the product's
  name** (`... 5 LƯỢNG ...`, `... 0,5 KG ...`, or nothing, which for a bar means
  one lượng). Everything is normalised to a price **per chỉ**, the unit
  Vietnamese gold is bought in. 1 lượng is 10 chỉ by definition.
- **The shop buys at one price and sells at another, and the default is the
  price the shop CHARGES** (`bán`), because that is what "the gold price" means:
  the news on 2026-10-11 said SJC was 144,8 triệu a lượng, and that is the shop's
  asking price, not what it pays. It is also the same basis as every other
  holding here — a stock, a fund and a crypto are valued at what they would cost
  to buy. `mua`, what the shop pays you, is the honest figure for "what could I
  get for this" and is one setting away. Both figures travel with the product,
  so the interface always shows the spread beside the one in use.

  This default was wrong in the first version, and the symptom was exactly the
  one to expect: an app showing a number 3,8 triệu a lượng below the figure in
  every newspaper headline. The default now lives in one place —
  `app.money.DEFAULT_GOLD_PRICING` — and the tests assert against the published
  news figure rather than against the code's own choice.

**Every gold price carries its unit, on screen as well as in the data.** The
shop publishes a price for its whole product line — one **lượng**, which is ten
chỉ — and the app stores it normalised to one chỉ. Both figures are therefore
shown, each labelled with the unit it is for: `14.360.000 ₫ / lượng` beside
`1.436.000 ₫ / chỉ`. A price with no unit beside it is the bug this guards: a
correct per-chỉ figure under a "/ lượng" label reads as a number that is ten
times wrong, which is how a user saw it and said so.
- **The payload is a list of one-key objects**, every field suffixed with its
  row number (`@n_1`, `@pb_1`, `@d_1`), so rows are read by their own number.
- **Not every line states its weight.** `ĐỒNG XU VRTL 0.1` is a coin whose name
  gives no unit; read as the default one lượng it came out at 139 600 ₫ a chỉ,
  a tenth of what gold costs. Rather than guess, every line is compared with the
  **middle of the list** — gold is one metal on one day, so its lines cannot
  differ by an order of magnitude — and a line that does is dropped. A guessed
  weight is wrong by a factor of ten and says nothing.

A holding points at a product line by a normalised **key**, not by its display
name, because the shop edits its names. A key that no longer appears is reported
as unpriced and left out of the total: re-pointing it at whatever is first in
the list would value it wrongly and say nothing.

Two more facts about this particular shop, which are why `app/net.py` exists:
its server does not send the intermediate certificate, so the platform trust
store rejects it while `certifi` accepts it; and the same payload carries the
shop's **silver** lines, which are filtered out — offering someone a silver bar
when they asked for gold is worse than offering nothing.

## 6. API

All paths under `/api`. Requests and responses are JSON. Local-only; CORS
allows `localhost:5173` for development.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | liveness |
| GET | `/api/settings` | base currency, language, supported lists |
| PATCH | `/api/settings` | change base currency / language |
| POST | `/api/settings/wipe` | delete all records (positions, sales, cash, movements, deposits, gold, history) |
| GET | `/api/assets` | list positions (filters: `kind`, `q`) |
| POST | `/api/assets` | create |
| GET | `/api/assets/{id}` | read one |
| PATCH | `/api/assets/{id}` | update |
| POST | `/api/assets/{id}/price` | refresh this one position's quote |
| POST | `/api/assets/{id}/sell` | sell part or all of it; keeps the gain it locked in |
| DELETE | `/api/assets/{id}` | delete, **refunding what the cash account paid** (200 with the movement, not 204) |
| GET | `/api/realized` | closed positions, newest first |
| DELETE | `/api/realized/{id}` | forget one recorded sale (the position is not restored) |
| GET | `/api/cash` | the two balances (VND, USD), creating them if missing |
| POST | `/api/cash/{id}/entry` | money in or out of a balance, with a reason |
| PATCH | `/api/cash/{id}` | **edit balance** (the manual update), label or note — records the difference |
| GET | `/api/deposits` | list term deposits (filter `matured`) |
| POST | `/api/deposits` | open a term deposit |
| GET | `/api/deposits/{id}` | read one, valued for today |
| PATCH | `/api/deposits/{id}` | change the terms |
| DELETE | `/api/deposits/{id}` | delete |
| GET | `/api/deposits/{id}/schedule` | value from today to maturity |
| POST | `/api/deposits/{id}/roll` | roll a matured deposit into a new term |
| POST | `/api/deposits/{id}/withdraw` | close it and record the cash |
| GET | `/api/gold/products` | the goldshop's lines, per chỉ (filter `q`, `fresh`) |
| GET | `/api/gold` | gold holdings, valued at the shop's price |
| POST | `/api/gold` | add a holding (the product key is checked against the shop) |
| GET | `/api/gold/{id}` | read one |
| PATCH | `/api/gold/{id}` | change the weight, the unit or the price basis |
| DELETE | `/api/gold/{id}` | delete |
| GET | `/api/portfolio` | valued portfolio + allocations + totals + every cash movement |
| GET | `/api/portfolio/history` | valuation series |
| POST | `/api/portfolio/snapshot` | write today's valuation |
| POST | `/api/prices/refresh` | refresh quotes for all market assets |
| GET | `/api/prices` | cached quotes |
| GET | `/api/market/search?q=` | resolve a name/symbol → suggestions |
| POST | `/api/fx/refresh` | refresh FX rates |

---

## 7. Frontend

React 19 + TypeScript + Vite + Tailwind v4 + Recharts. Single-page app, five
views:

1. **Dashboard** — total net worth in base, split by kind, allocation donut with
   percentages, gains, net-worth line chart, unconverted/stale warnings. The
   five kinds are always all listed, including the empty ones. The two gain
   tiles are the **unrealised** ones and say so; when anything has been sold, a
   second row adds the **realised** gain and the **total** across both — the row
   only appears once there is a realised figure to show.
2. **Holdings** — table of market assets with live value, cost, gain %, CRUD via
   a slide-over form; a symbol picker backed by `/api/market/search`. A row's
   action menu offers **Sell** (how many units went, how much came back), and
   under the table is the list of closed positions with what each released and
   locked in. The sell form shows the market value of the part being sold as a
   *reference beside the field* and never fills the amount in: a sale recorded
   at the market's own number would print unrealised gain as realised gain,
   which is the confusion the form exists to remove.
3. **Cash** — the balance in đồng and the balance in dollars, with **money in
   and out** (an amount, a direction, a date and a reason), edited in place when
   you would rather just type the number, and the **history** of every movement
   with what caused it, filterable to one balance. There is no "add a balance"
   and no "delete": there is nothing to add them to.
4. **Gold** — each holding as a card: the product line it follows, the shop's
   published price, that price per unit of the unit held, the value, and the
   gain. A holding on a line the shop no longer publishes says so instead of
   being valued at another line's price.
5. **Savings** — term deposits as cards: the bank, the rate, the term so far as
   a bar, value today, interest accrued, value at maturity, and the growth to
   maturity. A matured deposit is highlighted and carries the two actions that
   make sense — roll it over, or withdraw it into a cash account.
6. **Market** — cached quotes and FX rates with their dates, refresh buttons.
7. **Settings** — base currency, language, **whether trades move cash**, data
   location, and a danger zone that wipes every record behind a confirmation. The wipe keeps the settings and the
   cached prices and rates: they are not the user's data, and throwing away a
   rate would leave a fresh start unable to convert anything.

### 7.1 i18n

- A hand-rolled dictionary (`src/i18n/`), no library. `vi` and `en` trees are
  typed against the same `Dict` interface, so a missing key is a **compile
  error**, not a blank label.
- The chosen language is stored in `settings` on the server and mirrored in
  `localStorage` so the first paint is already in the right language.
- Numbers and currencies format through `Intl.NumberFormat` with a `vi-VN` /
  `en-US` locale chosen by language, not by currency.

---

### 7.1b Refreshing

Refresh lives in the header, once. What it did is reported underneath it, per
symbol: a feed that answered for nineteen holdings and not the twentieth is one
line of news, not a failure of the page. The report is kept in application
state rather than returned to the button, because the button is in the header
and has nowhere to render it.

### 7.2 Naming rules the UI follows

- A figure that is unknown renders with its **reason**, never as a dash: a dash
  teaches the reader nothing about what to do next. The reason codes are shared
  with the backend (`unpriced`, `not_convertible`, `no_quantity`, `no_cost`).
- `no_cost` is not "not counted". A position with no recorded cost has a real
  value and is inside the total; only its gain is withheld.
- A blank asset name falls back to the symbol: a nameless row is unreadable, and
  refusing the whole edit over a cleared field is worse. A genuinely empty name
  is a `422`.

## 8. Non-functional

| Concern | Decision |
|---|---|
| Deposit interest | Simple, actual days over 365, stops at maturity, never compounded |
| Storage | `backend/data.db`, SQLite, schema created at startup |
| Runtime | Python ≥ 3.12 via `uv`, Node ≥ 22 via `pnpm` |
| Serving | FastAPI serves the built `frontend/dist`; one URL, port `8010` |
| Tests | `pytest` (network never touched), `node --test` for pure TS helpers |
| Privacy | No telemetry, no accounts; only outbound calls are Yahoo + FX feed |
| Failure | Network failure degrades to cached/stale values, never a 500 page |

---

## 9. Acceptance criteria

1. `./start.sh` builds the frontend, starts the API and opens the app on
   `http://localhost:8010`.
2. Adding `AAPL` × 10 and `VIC.VN` × 1000 shows both valued in one base
   currency, with the FX used and its date.
2b. Opening a deposit of 1 000 000 000 ₫ at 6 %/year on a date 365 days ago shows
   exactly 60 000 000 ₫ of interest, and the same figure in the base currency.
3. Adding a cash account in VND and one in USD sums correctly into the base.
4. Editing a cash balance is possible in one interaction from the Cash page.
5. Switching base currency VND↔USD re-expresses every total; history keeps the
   base each point was written in.
6. Switching language vi↔en translates every visible label, with no missing
   keys and no untranslated fallback strings.
7. Attempting to store a currency other than VND/USD is rejected by the API.
8. `pytest` passes with the network unavailable.
9. A matured deposit offers roll-over and withdrawal; withdrawing it leaves the
   portfolio total unchanged, because the money moved rather than appeared.
10. No goal, chat, agent, or advisor code exists anywhere in the tree.
11. Selling a position at the price the market is quoting leaves the portfolio's
    **total gain unchanged** — the same money, moved from unrealised to
    realised — and the position itself is gone from the holdings table while
    the sale remains in `GET /api/realized`. Deleting a position must not be the
    way to record a sale.
12. With cash-linked trades **on**, buying takes exactly the cost out of the
    balance in that trade's own currency, selling puts back exactly the
    proceeds, and the portfolio's **total is unchanged by either**: money moved
    between two tables, it was not created. A dollar trade moves the dollar
    balance and leaves the dong one alone. Deleting that position gives back what
    the balance paid, and deleting one recorded while the link was **off** gives
    back nothing.
13. There is exactly one cash balance per currency: `POST /api/cash` and
    `DELETE /api/cash/{id}` do not exist, and a database that held two balances
    in one currency before this rule is merged at startup — balances added,
    history carried across, and a copy of the file written beside it first.
14. Money can be put into a balance and taken out of it with a reason
    (`POST /api/cash/{id}/entry`), and **the balance always equals the sum of
    its history**: a typed-in balance and a counted-and-corrected one leave a
    line too, and money that predates the history gets one opening line rather
    than a silent figure.
