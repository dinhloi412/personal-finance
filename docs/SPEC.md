# SoTaiSan — Đặc tả / Specification

A minimal, self-hosted personal **asset tracker**. Clone-inspired by
[aurelio-finance](https://github.com/LosaLosSantos/aurelio-finance) but reduced
to one job: **keep track of what you own and what it is worth.**

---

## 1. Scope

### 1.1 In scope

| # | Capability |
|---|---|
| 1 | Track **4 asset kinds**: `stock`, `fund` (ETF / mutual fund), `crypto`, `cash` |
| 2 | Market assets (`stock`, `fund`, `crypto`) priced automatically from Yahoo Finance |
| 3 | `cash` is a **manual balance** the user edits by hand when it moves |
| 4 | **2 currencies**: `VND`, `USD` — one is the *base* for all totals |
| 5 | **2 languages**: `vi` (Tiếng Việt), `en` (English) |
| 6 | Net-worth snapshot history + allocation breakdown |
| 7 | Everything local: SQLite file on disk, no account, no cloud |

### 1.2 Explicitly **out of scope**

- ❌ Goals / targets / planning of any kind
- ❌ AI advisor, chat, agents, MCP server, OpenRouter, web search
- ❌ Income, expenses, budgets, cash-flow analysis
- ❌ Debts, liabilities, mortgages, real assets, insurance, pensions
- ❌ Accumulation plans (PAC), recurring buys, dividend catch-up engine
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
                                    rates_json (currencies used + rates)
```

### 2.1 Why cash is its own table

Cash has no quantity, no symbol, no price and no cost basis. Forcing it into
`Asset` would mean five nullable columns and a permanent `if kind == "cash"`
branch in every read. It is a balance with a name. It gets a table.

### 2.2 Why an Instrument registry

A symbol is not a name. `VIC.VN` is "Vingroup", `BTC-USD` is "Bitcoin". Storing
the name beside the symbol means the day Yahoo renames a listing the user's
portfolio does not become a wall of tickers. The registry is *identity only* —
it never holds a price (that is `PriceCache`, which is dated and therefore
disposable).

### 2.3 Money arithmetic

- Every stored amount carries the currency it is in. There is no unit-less
  number anywhere in the schema.
- A `Valuation` is written **in the base currency that was in force when it was
  written** and records that base in `rates_json`. Changing the base currency
  later never rewrites history, and the chart says which base each point used.
- Floats, not Decimal: this is a tracker, not a ledger. Amounts are rounded for
  display only.

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

- Source: `yfinance` (Yahoo Finance). The most recent **close** from a short
  history window is used; Yahoo's realtime quote endpoint is unreliable.
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

---

## 5. Valuation

```
market position value_in_listing_ccy = quantity × price
value_in_base = convert(value, price_currency → base)
cost_in_base  = convert(cost_basis, asset_currency → base)
gain          = value_in_base − cost_in_base        (null if cost is null)
cash value    = convert(balance, cash currency → base)
total         = Σ market values + Σ cash values
```

- `total` is the sum of conversions, never a sum across mixed units.
- Any position that could not be converted is excluded from `total` and listed
  in `unconverted[]` so the number is never quietly short.

---

## 6. API

All paths under `/api`. Requests and responses are JSON. Local-only; CORS
allows `localhost:5173` for development.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | liveness |
| GET | `/api/settings` | base currency, language, supported lists |
| PATCH | `/api/settings` | change base currency / language |
| POST | `/api/settings/wipe` | delete all records (positions, cash, history) |
| GET | `/api/assets` | list positions (filters: `kind`, `q`) |
| POST | `/api/assets` | create |
| GET | `/api/assets/{id}` | read one |
| PATCH | `/api/assets/{id}` | update |
| DELETE | `/api/assets/{id}` | delete |
| POST | `/api/assets/{id}/price` | refresh this one position's quote |
| GET | `/api/cash` | list cash accounts |
| POST | `/api/cash` | create |
| PATCH | `/api/cash/{id}` | **edit balance** (the manual update) |
| DELETE | `/api/cash/{id}` | delete |
| GET | `/api/portfolio` | valued portfolio + allocations + totals |
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

1. **Dashboard** — total net worth in base, split by kind, allocation pie, gains,
   net-worth line chart, unconverted/stale warnings.
2. **Holdings** — table of market assets with live value, cost, gain %, CRUD via
   a slide-over form; a symbol picker backed by `/api/market/search`.
3. **Cash** — list of cash accounts, inline balance editing (the manual
   update), per-currency subtotals.
4. **Market** — cached quotes and FX rates with their dates, refresh buttons.
5. **Settings** — base currency, language, data location, and a danger zone that
   wipes every record behind a confirmation. The wipe keeps the settings and the
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
3. Adding a cash account in VND and one in USD sums correctly into the base.
4. Editing a cash balance is possible in one interaction from the Cash page.
5. Switching base currency VND↔USD re-expresses every total; history keeps the
   base each point was written in.
6. Switching language vi↔en translates every visible label, with no missing
   keys and no untranslated fallback strings.
7. Attempting to store a currency other than VND/USD is rejected by the API.
8. `pytest` passes with the network unavailable.
9. No goal, chat, agent, or advisor code exists anywhere in the tree.
