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
| M10 dialogs | done | the overlay wrapper measured in a browser across all four dialogs; `pnpm test` now 22 |
| M11 dropdowns | done | every select draws its own chevron with room on both sides; measured on all four pages and in the dialogs |
| M12 open-ended funds | done | `app/funds.py` + `tests/test_funds.py` (34), and the two funds the user actually holds priced from the live Fmarket |
| M13 Vietnamese gold | done | `app/gold.py` + `tests/test_gold.py` (42), priced from the live Bảo Tín Minh Châu list |

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
- **Every dropdown's arrow touched its right border.** `appearance: none` plus a
  drawn chevron, because a native arrow cannot be positioned: every browser
  puts it hard against the edge whatever padding the control has, so text 12px
  from the left ended with an arrow 0px from the right. Four pages and two
  dialogs measured afterwards: 40px of padding, the chevron 14px inside.
- **Every dialog was a third of the width it asked for.** The overlay wrapped
  its panel in a bare `<div>`, and a flex item is sized by its content: the cash
  form measured 229px, so the panel's `w-full max-w-lg` was resolved against a
  229px parent and the `512px` was never reached. Measured with CDP rather than
  guessed — the panel was 229px wide while claiming `max-width: 512px`. Giving
  the wrapper `w-full` fixed the width and broke the centring in the same
  stroke, because a full-width wrapper takes the centring with it; both are now
  asserted by a test that reads the component. Two of the four dialogs are
  slide-overs and had to keep their right alignment, which is why the wrapper
  places the panel rather than the backdrop.
- **Nothing showed a pointer.** Tailwind v4 sets `cursor: default` on buttons,
  so every control in the app looked inert. Fixed with one rule, and the first
  version of that rule still missed the labels tied to a control by `for` — the
  Holdings filter read "arrow" over the word and "hand" over the box under it.
  A browser check (CDP, every control on every page) is what settled it: a
  screenshot cannot show a cursor.

## M12 — Open-ended funds (the second price source)

Asked for because the two funds the user holds — `VNDAF` and `DCDE` — could not
be found at all. They are not missing from the app: they are missing from Yahoo,
and for a reason worth stating once.

**A fund certificate is not a listing.** An open-ended fund has no ticker and no
session close; what it has is a NAV, published once a day by its management
company. So this is not a gap in the search, it is a second kind of price, and
it gets a second source rather than a workaround.

Where it went, and why:

- **`app/funds.py`** — Fmarket's public JSON API. Chosen over Dragon Capital's
  own site because that site publishes the same numbers as an HTML table, and a
  scraper for a page nobody promised to keep is a cost this does not need to
  pay. Fmarket answers with `nav` and `lastNAVDate`: the number and the day it
  is for.
- **`pricing._sources_for`** — the order is "the source that priced it last
  time, then the other one". A fund does not become listed and a stock does not
  start publishing a NAV, so trying the wrong source first costs a request on
  every refresh and, worse, a delay.
- **`price_cache.source`** — which feed answered, so the next refresh knows
  where to start and the interface can say whether a number is a close or a
  NAV. They are not the same kind of fact.
- **The alias table.** Fmarket uses the fund company's internal code for Dragon
  Capital's funds; the certificate uses another. `DCDE` is `VFMVF4`. Both work,
  and the picker shows both names so one fund cannot be mistaken for two. The
  mapping is four rows and a test, not a heuristic: the NAVs were cross-checked
  against Dragon Capital's own published price list and matched to the dong.

Two things the API does that shaped the code, both found by trying it rather
than reading about it:

1. **`/products/{id}` takes a numeric id, not a code.** Asking for
   `/products/VNDAF` answers `400` before any lookup, and the error says only
   "HTTP Error 400" — which is what a wrong-shaped request looks like from a
   distance. The code now resolves the code to its id through the catalogue,
   which is fetched once and remembered for six hours.
2. **There is no NAV history endpoint.** Eight shapes of URL were tried; the
   series is not public. So a fund's value is always current NAV, and a dated
   valuation of a fund cannot be reconstructed from this source. The price
   cache says which day each NAV is for, which is what keeps that honest rather
   than silent.

## M13 — Vietnamese gold

Asked for after the funds, and the request itself corrected my first attempt:
I started building **world** gold (Yahoo's gold contract) plus a manual entry,
on the assumption that a domestic price would not be available. The user came
back with *"theo vàng VN nha, tôi không theo vàng thế giới, xem có API hay gì
tương tự để get dc ko"* — track Vietnamese gold, look for an API. So I looked
properly, and there is one.

**`api.btmc.vn` — Bảo Tín Minh Châu's public price API.** Plain JSON, no key,
`mua` and `bán` for 21 products, each stamped with the minute it changed. SJC,
DOJI and BTMC's own web pages all render their prices with JavaScript, so the
API is not a shortcut around scraping — it is the only machine-readable source.
Verified against the page: SJC 14 100 000 ₫/lượng, matching the site.

Six things were found by working with the real payload rather than a sample:

1. **The payload is a list of one-key objects.** Every field is suffixed with
   its row number (`@n_1`, `@pb_1`, `@d_1`), so a row must be read by its own
   `@row`. Positional parsing yields a table of nothings.
2. **The unit is written only inside the product's name.** `VÀNG MIẾNG SJC` is
   per lượng, `VÀNG NGUYÊN LIỆU` per chỉ, and the payload does not say which.
   Everything is normalised to per chỉ.
3. **`5 LƯỢNG` parsed as "5 grams"** — the word ends in `g`, and a careless unit
   pattern read that as grams, so a bar came out **fifty times** too small. Fixed
   with a lookbehind; the test that would have caught it now says so.
4. **Not every line states its weight.** `ĐỒNG XU VRTL 0.1` is a coin with no
   unit in its name; read as the default one lượng it was 139 600 ₫ a chỉ, a
   tenth of the price of gold. Rather than guess, lines are compared with the
   **middle of the list** — one metal on one day cannot differ by an order of
   magnitude — and the outlier is dropped. Trading a missing product for a
   factor-of-ten error is not a trade worth making.
5. **The server does not send its intermediate certificate**, so the platform
   trust store rejected it while `curl` and `certifi` accepted it. That is why
   `app/net.py` exists: one place that knows how to open an HTTPS connection, so
   a feed added later gets the working behaviour by default.
6. **The same payload carries the shop's silver.** Filtered out on the product
   name: offering someone a silver bar when they asked for gold is worse than
   offering nothing.

**The world-price version was deleted rather than kept as a fallback.** Two
price sources for one holding is two ways to be wrong, and the user was explicit
about which one they track.

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
| A gold holding valued at the wrong unit | The unit is parsed from the shop's own name, everything is normalised to one unit, and a line whose weight cannot be read is dropped rather than guessed |
| A hand-entered price silently reused for years | Removed: gold is priced from the shop, and a manual price is no longer a mode |
| A fund that silently looks unpriced | A second source for NAVs, an alias table for the one fund with two names, and a `source` column so a NAV is never shown as a close |
| An interface that looks inert | One cursor rule over the interactive elements, asserted by `tests/cursor.test.ts` and checked in a browser with CDP |
| A dialog sized by its content instead of its own `max-w-*` | The overlay wrapper is `w-full` and places its panel; asserted by test and measured with CDP across all four dialogs |
| An existing database missing a new column | `add_missing_columns()` at startup, tested against a deliberately old-shape database |
| Compounding a deposit the way the bank does not | Simple interest on actual days over 365, asserted against hand-checkable figures |
| Counting withdrawn money twice | Withdrawal closes the deposit and writes the cash in one request, and a test asserts the total is unchanged |
| Float rounding on VND (large integers) | Round for display only; VND shown with 0 decimals |

## Order of work

M0 → M1 → M2 → M3 → M4 are strictly sequential (API depends on valuation
depends on FX/prices depends on models). M5 needs only the frozen API shape
from SPEC §6, so its scaffolding starts in parallel with M2/M3. M6 closes both.
