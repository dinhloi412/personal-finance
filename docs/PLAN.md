# SoTaiSan — Kế hoạch triển khai / Implementation Plan

Companion to [SPEC.md](./SPEC.md). Seven milestones; each ends in something
runnable, so a mistake is found in the milestone that made it.

---

## M0 — Skeleton & toolchain

- `backend/pyproject.toml` (uv): `fastapi`, `uvicorn[standard]`, `sqlalchemy`,
  `yfinance`, `pydantic`, dev `pytest`, `httpx`.
- `frontend/package.json`: `react`, `react-dom`, `vite`, `typescript`,
  `tailwindcss` + `@tailwindcss/vite`, `recharts`.
- `docs/`, `.gitignore`, `README.md`.
- **Done when:** `uv run python -c "import fastapi, yfinance"` and
  `pnpm build` both succeed on an empty app.

## M1 — Database, models, settings

- `app/database.py` — engine, `SessionLocal`, `get_db`, `init_db()` creating
  tables from metadata, SQLite `foreign_keys=ON`.
- `app/models.py` — `Instrument`, `Asset`, `CashAccount`, `PriceCache`,
  `FxRate`, `Valuation`, `Setting` exactly as in SPEC §2.
- `app/settings_store.py` — read/write `base_currency` (default `VND`) and
  `language` (default `vi`), validated against the supported literals.
- **Done when:** a fresh `data.db` is created with all 7 tables.

## M2 — Market data and FX

- `app/market.py`
  - `search(query)` → `yfinance.Search`, normalised to
    `{symbol, name, kind, exchange, currency}`; falls back to a plain quote
    lookup when search returns nothing (so a raw `VIC.VN` still resolves).
  - `quote(symbol)` → latest close + currency + `as_of`, via
    `Ticker.history(period="10d")`.
  - `resolve_kind()`, `resolve_currency()` helpers.
  - Every network call is a module-private `_fetch_*` so tests monkeypatch it.
- `app/fx.py`
  - `refresh_rates(session, base)` → fetch `open.er-api.com` once, store rows
    for VND and USD against `base`.
  - `rate_on(session, base, currency, day)` → exact day, else newest older,
    else seed constant flagged `stale`.
  - `Converter(session, base)` — `to_base(amount, currency)` → `float | None`,
    plus `.rate_info(currency)` for the UI.
- **Done when:** `pytest` proves the seeded rate is used offline and that
  conversion through a USD-based feed answers for VND.

## M3 — Valuation

- `app/valuation.py`
  - `value_asset(asset, price_row, converter)` → listing value, base value,
    base cost, gain, `priced`, `unconverted_reason`.
  - `value_cash(account, converter)`.
  - `portfolio(session)` → `{base_currency, total, market_value, cash_value,
    by_kind[], by_currency[], assets[], cash[], unconverted[], fx[]}`.
  - `write_snapshot(session)` → upsert today's `Valuation`.
  - `history(session)` → series in written order.
- **Done when:** a mixed VND/USD portfolio sums to one base number and the
  unmatched-currency case is excluded and reported.

## M4 — API

- `app/schemas.py` — Pydantic v2 models with `Literal["VND","USD"]`,
  `Literal["stock","fund","crypto"]`, `Literal["vi","en"]`.
- `app/routers/` — `assets.py`, `cash.py`, `portfolio.py`, `market.py`,
  `settings.py`, shared `deps.py` (one `get_or_404`, one session dep).
- `app/main.py` — CORS for `:5173`, routers, `GET /api/health`, static mount of
  `frontend/dist` with an SPA fallback.
- **Done when:** `/docs` lists every endpoint in SPEC §6 and each one answers.

## M5 — Frontend

- `src/i18n/{types.ts,vi.ts,en.ts,index.tsx}` — provider + `useT()`, typed
  against one `Dict` interface; locale-aware `formatMoney`, `formatPercent`,
  `formatDate`, `formatQty`.
- `src/api/` — thin `fetch` client, one function per endpoint, types mirroring
  the schemas.
- `src/state/AppContext.tsx` — settings + portfolio, one `refresh()`.
- `src/components/ui.tsx` — button, card, input, select, modal/slide-over,
  table, badge, empty state, sparkline, pie, bars.
- Views: `Dashboard.tsx`, `Holdings.tsx`, `Cash.tsx`, `Market.tsx`,
  `Settings.tsx`, `App.tsx` (nav + routing), `InstrumentPicker.tsx`.
- **Done when:** `pnpm build` is green and every SPEC §9 acceptance item can be
  clicked through.

## M6b — Term deposits (added after the first build)

Asked for after the app was working, and the interesting part was deciding
*where* it goes rather than how to write it.

**It is a fifth kind of holding, not a variety of cash.** The question "should a
deposit live in the cash table?" has a clear answer once the source of value is
named:

| | where the value comes from | who decides it |
|---|---|---|
| market position | a quote from outside | the market |
| cash | a balance the user counted | the user |
| **term deposit** | **the agreement: principal, rate, days held** | **the contract** |

Folding it into cash would mean either making the user retype a figure the app
can derive from terms it already knows, or storing the principal and losing the
interest — which is the only reason to track a deposit at all. So:

- `app/models.py` — a `deposits` table: principal, rate, start, maturity,
  interest mode. Not one nullable column added to cash.
- `app/deposits.py` — the interest arithmetic, alone, with no session and no
  rate table in it, so it can be tested as arithmetic.
- `app/valuation.py` — `value_term_deposit` converts what `deposits.py`
  computed. Interest is computed in the deposit's own currency FIRST and
  converted second; doing it the other way applies a rate to the wrong number.
- `frontend/src/views/Savings.tsx` — its own page, because a card with two
  dates, a rate and a projection is not a table row.
- `api/deposits` — including the two endpoints that only exist here, `roll` and
  `withdraw`, because each moves money between two tables.

**Three conventions, each of which a reader could have chosen differently:**

1. **Simple interest, actual days, 365-day year.** Daily compounding would
   overstate every figure by about 1.4 % and would not match the bank.
2. **Interest stops at maturity.** The contract rate is not being paid after
   the maturity date; carrying it forward would invent income. The record is
   marked `matured` instead, and offers the decision that is actually waiting.
3. **A null maturity date is a demand deposit**, which never matures and keeps
   accruing — the only holding in the app whose value rises with nobody doing
   anything.

**Two values, not one.** "Value today" and "value at maturity" are both shown.
The first alone hides why the deposit is held; the second alone claims money
that has not been earned.

**One bug found while building it, and it was not in the new code.**
`create_all` does not alter an existing table, so adding `deposits` and
`valuations.deposit_value` broke every database written by the previous build —
`no such column: valuations.deposit_value`, raised from an unrelated request, on
the user's only copy. `app/database.py` now has `add_missing_columns()`, which
adds what the models declare and the database lacks, and touches nothing else.
`tests/test_schema_upgrade.py` builds an old-shape database on purpose and
proves the upgrade, because the rest of the suite builds its schema from the
models and could never have caught this.

## M6 — Tests, demo data, run script

- `backend/tests/` — `conftest.py` (in-memory SQLite, monkeypatched network),
  `test_market.py`, `test_fx.py`, `test_valuation.py`, `test_api.py`,
  `test_settings.py`, `test_scope.py` (guards: no goals/chat/agent modules, no
  currency outside VND/USD).
- `app/seed.py` — optional demo portfolio (only on an empty DB, `--demo`).
- `backend/tests/` frontend: `frontend/tests/i18n.test.ts` (key parity between
  `vi` and `en`), `format.test.ts`.
- `start.sh` — build frontend, run uvicorn on `:8010`, open the browser.
- **Done when:** `uv run pytest` and `node --test` pass.

## M7 — Verify

1. `uv run pytest -q` → all green, no network.
2. `pnpm build` → clean, no TS errors.
3. `./start.sh --no-browser` → `curl /api/portfolio` returns 200 with a real
   quote and a real FX rate for `AAPL` + `VIC.VN` + cash VND/USD.
4. Delete the test rows; leave the user's DB empty and ready.

---

## Status — as built

| Milestone | State | Evidence |
|---|---|---|
| M0 skeleton | done | `uv sync`, `pnpm install` |
| M1 database & settings | done | 7 tables, seeded on first start |
| M2 market & FX | done | `tests/test_market.py`, `tests/test_fx.py` |
| M3 valuation | done | `tests/test_valuation.py` |
| M4 API | done | `tests/test_api.py`, 18 routes asserted in `test_scope.py` |
| M5 frontend | done | `pnpm build`, 13 node tests |
| M6 tests, demo, run script | done | **170 backend tests pass**, `app/seed.py`, `start.sh` |
| M6b term deposits | done | `tests/test_deposits.py` (23), `test_api.py::TestDeposits` (20), `tests/test_schema_upgrade.py` (5) |
| M7 verify | done | live run against Yahoo + the FX feed on port 8010; `scripts/acceptance.sh` green, 11 sections |
| M8 UI pass | done | every page screenshotted and read at 1440 and (via CDP) 390; `pnpm test` now 21 |
| M9 cursors | done | one rule in `index.css`, a test that reads it, and a CDP probe of every page as proof |

The screenshot pass found six more, all fixed: the allocation donut measured
zero height inside a grid cell and never drew; a one-point history chart drew an
empty box with a floating dot; the Overview duplicated the header's refresh
button; the allocation legend had no percentages and its swatches were indexed
differently from the slices; table cells were padded at 8px so the Cash header
read as run-together words; and deposits were missing from the allocation
entirely until they were added to the frontend's kind list — the API had been
returning them all along.

Two more things the frontend work surfaced, and what was done about them:

- **A cleared asset name could have been a 500.** `assets.name` was
  `nullable=False`, so `PATCH {"name": null}` would have hit a NOT NULL
  constraint. The column is now nullable (the schema is the thing that should
  refuse it), `AssetUpdate.name` has `min_length=1`, and the router substitutes
  the symbol for a name of nothing. Covered by `TestANameThatWouldBeNothing`.
- **SPEC §7.5 promised a wipe and the API had none.** Added
  `POST /api/settings/wipe`, which removes positions, cash and history and
  keeps the settings and the cached prices and rates — a fresh start must still
  be able to convert what the user types in next.

Seven things were found by verifying rather than by building, and each changed
the design. The first three came from the API, the rest from screenshotting
every page and reading the result:

- **A refresh only knew one base.** The first live run switched the display
  currency to USD and got a total of 3 000 instead of 20 339, because no rate
  had ever been fetched in that direction — every dong position was
  unconvertible. `pricing.refresh_all_fx` now covers every base the user can
  switch to, and `tests/test_api.py::test_switching_the_base_never_leaves_a_position_unconverted`
  pins it down.
- **The base currency appeared in the "rates used" report** as a conversion at
  1.0. It is the base: it is not converted, and saying otherwise invites a
  reader to think a rate was applied. `fx.Converter.rate_for` now excludes it.
- **A placeholder rate was indistinguishable from a real one on any given
  day.** `Rate.stale` now means "not published for the day asked", so a rate
  carried over from another day is labelled exactly like the seed.
- **The allocation chart drew nothing.** It was not a zero-height grid cell —
  the DOM measured 527×200. Recharts animates a `Pie` in by default, and both
  a screenshot and a slow machine capture the frame before it draws. Every
  chart in the kit now sets `isAnimationActive={false}`, which is also why the
  line charts had always rendered.
- **`Th`/`Td` used 8px of padding**, so the Cash header read as one run of
  words. Now 12px, with a little more vertical room.
- **Deposits were missing from the allocation** for a few minutes, and the
  percentages exposed it immediately: the frontend's kind list is its own
  constant, so a new kind has to be added in two places, and the second one
  was forgotten. Worth knowing: the API had been returning it all along.
- **Nothing showed a pointer.** Tailwind v4 sets `cursor: default` on buttons,
  so every control in the app looked inert. Fixed with one rule, and the first
  version of that rule still missed the labels tied to a control by `for` — the
  Holdings filter read "arrow" over the word and "hand" over the box under it.
  A browser check (CDP, every control on every page) is what settled it: a
  screenshot cannot show a cursor.

## Risk register

| Risk | Mitigation |
|---|---|
| Yahoo throttles or blocks the network | Cached quote keeps serving; refresh reports failures per symbol |
| Yahoo symbol guessing (`VIC.VN` vs `VIC.HM`) | Search endpoint + free-text symbol field; the app never *needs* search to work |
| VND/other-currency quote mixed into a total | `unconverted[]` list; excluded from `total`, badge in the UI |
| Base-currency change rewriting history | `Valuation` stores the base it was written in |
| Base-currency change emptying the total | Both bases are seeded and both are refreshed |
| i18n drift (missing key) | One `Dict` interface for both trees + a parity test |
| Scope creep back toward the reference app | `test_scope.py` fails on a forbidden module name, on an AI-provider string, and on any API path outside the 19 the spec lists |
| A blank name reaching a NOT NULL column | Schema refuses it with a 422; the router substitutes the symbol |
| A dictionary key nothing reads | `pnpm test` fails on a declared key with no `t()` call behind it |
| A chart that renders nothing | Every chart sets `isAnimationActive={false}`; the kit's wrapper is `w-full min-w-0` with an explicit height |
| An interface that looks inert | One cursor rule over the interactive elements, asserted by `tests/cursor.test.ts` and checked in a browser with CDP |
| An existing database missing a new column | `add_missing_columns()` at startup, tested against a deliberately old-shape database |
| Compounding a deposit the way the bank does not | Simple interest on actual days over 365, asserted against hand-checkable figures |
| Counting withdrawn money twice | Withdrawal closes the deposit and writes the cash in one request, and a test asserts the total is unchanged |
| Float rounding on VND (large integers) | Round for display only; VND shown with 0 decimals |

## Order of work

M0 → M1 → M2 → M3 → M4 are strictly sequential (API depends on valuation
depends on FX/prices depends on models). M5 needs only the frozen API shape
from SPEC §6, so its scaffolding starts in parallel with M2/M3. M6 closes both.
