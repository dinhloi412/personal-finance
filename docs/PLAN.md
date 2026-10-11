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

**Two more, found after it shipped and because a user said the price looked
wrong.** They were right about the symptom and the number was right:

1. **The default landed on the wrong side of the spread.** The app valued gold
   at what the shop *pays* (141 triệu/lượng for SJC); every newspaper headline,
   and the whole market, means what the shop *charges* (144,8 triệu). The number
   was correctly read and correctly converted — it was the wrong one of the two.
   The default is now the asking price, which is also the same basis as every
   other holding in the app, and the labels say which is the market price.
2. **The default was declared in three places and they disagreed.** The
   vocabulary said `sell` after the fix, the model's Python-side default said
   `sell`, and the column's `server_default` still said `buy` — so a write that
   did not go through the ORM, or an INSERT that did not name the column, landed
   on the old value. A Python-side default is an ORM feature; the column needs
   its own. Both now come from one constant, and a test asks the API the
   question a client that has never heard of `pricing` would ask.

**And a third, when the user looked again:** the per-lượng label sat over a
per-chỉ figure. The shop publishes `14.360.000 ₫` for one lượng and the app
stores `1.436.000 ₫` for one chỉ; putting the stored figure under a "/ lượng"
label made a correct number look ten times wrong. Every gold price now carries
its unit, on the card and in the form, and the form spells out the per-lượng
equivalent so the two are never mistaken for each other.

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

## M14 — Selling a position, and keeping the gain (added after the app worked)

Asked for in one sentence — "if I sell that symbol, does the gain still count?" —
and the answer at the time was no: `DELETE /api/assets/{id}` removed the
position *and* the cost basis with it, so the portfolio's reported loss got
smaller every time a loser was sold. That is the one way this app could be used
to tell yourself a story, and it is why this milestone exists.

**The design question was where a sale lives, not how to subtract.**

- `app/models.py` — a `realized` table holding the *facts of the trade* in the
  currencies they happened in: `cost_removed` in the position's, `proceeds` in
  the market's. No FK to `instruments`: the row has to outlive the position, so
  it carries its own symbol, name and kind.
- `app/realized.py` — the proportional-cost arithmetic alone, with no session
  arithmetic and no conversion in it, so it can be tested as arithmetic. This is
  the `deposits.py` pattern applied to a second computation.
- `app/valuation.py` — `value_sale` derives every base-currency figure on read,
  exactly as `value_asset` does for a live position. A sale is a fact that
  gets converted, not a total frozen on a day; putting it in `Valuation`'s shape
  would have left a dong gain sitting in a dollar portfolio after a base switch.
- `POST /api/assets/{id}/sell`, `GET|DELETE /api/realized` — the sale itself, a
  way to read it, and a way back from one entered by mistake.
- `frontend/src/views/Holdings.tsx` — a **Sell** entry in the row menu and, under
  the table, the closed positions with what each released.

**Three decisions a reader could have made differently:**

1. **Average cost, not lots.** A position stores one total (`cost_basis`), so
   the cost a sale releases is `cost_basis × sold / held`. Recording the
   purchases would be a ledger, and §1.2 says there is not one.
2. **A fully sold position is deleted, not zeroed.** A zero-quantity row has no
   value, so it would appear in the dashboard's `unconverted` list telling the
   user that a position they have already sold is "not counted" — a warning
   about nothing. `remaining <= 1e-9` is a full sale, and the tolerance is there
   because `100 - 1e-14` is what a pre-filled form can send.
3. **Nothing is posted to cash.** Inventing a cash row from a sale would put
   money somewhere the user never said it went. They count their balances.

**The test that matters** is not that the arithmetic adds up — it is the
invariant: *selling at the price the market is quoting must leave the total gain
unchanged*, because the same money has only moved from unrealised to realised.
`TestTheDashboardTotals` asserts it, and `scripts/acceptance.sh` checks it
against a live server, because a sign error in the proportional cost would pass
every other test in the suite while quietly doubling a loss.

**One bug found on the way, in code that was already there.** `POST
/api/settings/wipe` — "Xoá toàn bộ dữ liệu" — deleted positions, cash and
history and left **term deposits and gold** behind, in the one feature whose
whole purpose is that nothing is left behind. Fixed in the same change, with a
test that asserts every table of records is listed, because a wipe is only as
complete as the list someone remembered to keep up to date.

## M15 — Cash-linked trades (added after the app worked)

Asked for as the next step after selling: *after the initial data is in, later
trades should take from cash and put back to cash, with a switch to turn that
off.* The switch is the whole design. While a portfolio is being typed in, the
holdings and the balance are two independent facts, and an app that moved money
during that pass would be correcting the user's arithmetic with its own.

**The decision that shaped the module was where the arithmetic lives.** Money
moving between two tables in six endpoints is six chances for a balance to
disagree with its own history, so there is one writer — `app/movements.py` —
and every endpoint is a sign and a reason on top of it. The balance is updated
by the same value the row records, in the same call.

**Four things a reader could have decided differently:**

1. **The user may override the amount.** A purchase of 1 500 USD paid from a
   dong account is a number of đồng that only the bank statement knows. The form
   pre-fills today's rate and lets it be corrected; the rate used is stored with
   the row.
2. **The browser never converts.** Pre-filling that figure needed a conversion
   on the client, which would have been a second place where the arithmetic
   lives — so `GET /api/fx/convert` exists instead. Writing it exposed a real
   bug on the first live run: `Converter.report()` lists only the rates it has
   *touched*, and asking before converting returned a figure with no date and no
   source. The fix is one line, and a test now asserts the provenance.
3. **A delete refunds `net_invested`, not the cost basis.** Bought for 10 000 000
   and half sold for 7 000 000, a position has 3 000 000 of the account's money
   in it — refunding the 5 000 000 of remaining cost would print money on the
   way out.
4. **The link never blocks the record.** No account, no rate, no cost: the trade
   is written and the response says which of the three stopped the cash side.
   The alternative loses the more important half of the transaction.

**A name the scope guard rejected.** The module was written as `cashflow.py`,
and `test_scope.py` failed it immediately: "cash-flow analysis" is a feature
this app was reduced *from*, and a module named after it is how a removed
feature comes back. It is `movements.py` now. The guard did its job, and
weakening the list instead would have removed the only thing standing between
this app and the project it was cut down from.

**One contract change worth naming.** `DELETE /api/assets/{id}` and its two
siblings answer `200` with the movement instead of `204`, because deleting is
now two acts and a client that could not tell whether the second one happened
would have to guess about a balance it is looking at.

## M16 — One cash balance per currency (asked for after M15)

The next request, almost immediately: *cash should be one source, accumulated
into, not split into accounts.* M15 had just given every trade a picker and a
`cash_account_id`, and the picker was the complaint — a choice nobody wanted,
protecting against a mistake nobody was going to make.

**Two balances, not one, and that is the whole design.** One pot would have to be
denominated in something, and a dollar purchase paid from a dong pot is a
conversion the user did at a counter. Two keep every trade in its own currency,
which is also what removed the conversion from the common path: a trade in
dollars moves the dollar pot, in the trade's own number, to the last decimal.

**What went with the picker.** `POST /api/cash` and `DELETE /api/cash/{id}`
were deleted rather than guarded — a route that cannot exist is a stronger
refusal than a validator rejecting its currency. `GET /api/fx/convert` was built
in M15 for a form to pre-fill a cross-currency amount, and with no
cross-currency amount to pre-fill it was deleted too; the lesson it taught (a
figure must carry its provenance) stayed, and the rate a movement records still
travels with its row.

**Three things the change had to get right, and each has a test:**

1. **The pots are always there.** Created at startup and again on any read, so
   "one balance per currency" is a property of the API rather than of someone
   having visited the Cash page. A wipe empties them instead of removing them.
2. **A currency with no pot falls back to đồng and reports it.** An EUR-quoted
   holding's sale is recorded and the cash side says `no_rate`, rather than
   reaching for a rate that does not exist.
3. **A deposit's payout is the one movement the switch does not govern.** With
   the link off there is still nowhere else for the money to go, and a balance
   that grew with no line of history is what the history exists to prevent.

**The migration is the interesting part.** Cash used to be a list, so an older
database can hold two dong balances — the user's own did, by the time this was
written. `merge_cash_pots` runs at startup, adds the balances together, moves the
movement history onto the surviving row instead of letting it cascade away with
the account, and **writes a copy of the database file beside it first**. That
last part is this repository's own rule (`app/database.py`: a migration needs a
copy of the file first), and `tests/test_schema_upgrade.py` builds a
constraint-free `cash_accounts` table by hand to prove the whole path, because
the rest of the suite builds its schema from the models and could never have
caught it.

## M17 — Money in and out of cash (asked for right after M16)

*"Isn't there a way to add money to cash?"* — and there was not. M16 had left the
Cash page with one way to change a balance: click it and type the new number.
That is the app's oldest idea (a balance you count), and it is not the same thing
as "5 000 000 arrived from my salary", which is an event with a reason and a day
of its own.

**The request exposed a gap the page was already claiming to fill.** The history
card said a balance is explained by the lines under it — while a typed-in balance
left no line at all. So this milestone is two things at once: an action that puts
money in and takes it out, and making every change to a balance leave a line.

**Three decisions:**

1. **A reason, not a category.** Free text, stored as text. The moment a reason
   becomes a category this app is a budgeting tool, which §1.2 refuses and
   `test_scope.py` enforces.
2. **A direction, not a sign.** `{"amount": 500000, "direction": "out"}` rather
   than `-500000`: a form that asks for a minus to mean a withdrawal is a form
   that will one day record one the wrong way round.
3. **The books balance, including backwards.** `reconcile` runs at startup and
   writes one opening line for money that was in a pot before there were lines,
   dated the day the balance was last counted. It is idempotent, and it writes a
   copy of the file first — the same rule as the merge next to it.

**What the live database showed.** By the end of this milestone the user's own
`data.db` had two dong accounts merged by their own run of the app, five
movements, and a balance of 20 100 000 ₫ against a history summing to zero —
money that predates the history, exactly the case `reconcile` exists for. On the
next start it gets one line, and from then on the page's claim is true.

## Risk register

| Risk | Mitigation |
|---|---|
| Yahoo throttles or blocks the network | Cached quote keeps serving; refresh reports failures per symbol |
| Yahoo symbol guessing (`VIC.VN` vs `VIC.HM`) | Search endpoint + free-text symbol field; the app never *needs* search to work |
| VND/other-currency quote mixed into a total | `unconverted[]` list; excluded from `total`, badge in the UI |
| Base-currency change rewriting history | `Valuation` stores the base it was written in |
| Base-currency change emptying the total | Both bases are seeded and both are refreshed |
| i18n drift (missing key) | One `Dict` interface for both trees + a parity test |
| Scope creep back toward the reference app | `test_scope.py` fails on a forbidden module name, on an AI-provider string, and on any API path outside the set the spec lists |
| A blank name reaching a NOT NULL column | Schema refuses it with a 422; the router substitutes the symbol |
| A dictionary key nothing reads | `pnpm test` fails on a declared key with no `t()` call behind it |
| A chart that renders nothing | Every chart sets `isAnimationActive={false}`; the kit's wrapper is `w-full min-w-0` with an explicit height |
| A gold price that is right in the data and wrong on screen | Every gold figure is labelled with the unit it is for, and the one place the frontend converts between units is a named constant with a test |
| A gold price on the wrong side of the spread | One declared default, asserted against the figure the news publishes rather than against the code's own choice |
| A gold holding valued at the wrong unit | The unit is parsed from the shop's own name, everything is normalised to one unit, and a line whose weight cannot be read is dropped rather than guessed |
| A hand-entered price silently reused for years | Removed: gold is priced from the shop, and a manual price is no longer a mode |
| A fund that silently looks unpriced | A second source for NAVs, an alias table for the one fund with two names, and a `source` column so a NAV is never shown as a close |
| An interface that looks inert | One cursor rule over the interactive elements, asserted by `tests/cursor.test.ts` and checked in a browser with CDP |
| A dialog sized by its content instead of its own `max-w-*` | The overlay wrapper is `w-full` and places its panel; asserted by test and measured with CDP across all four dialogs |
| An existing database missing a new column | `add_missing_columns()` at startup, tested against a deliberately old-shape database |
| Compounding a deposit the way the bank does not | Simple interest on actual days over 365, asserted against hand-checkable figures |
| Counting withdrawn money twice | Withdrawal closes the deposit and writes the cash in one request, and a test asserts the total is unchanged |
| Selling a position making its loss disappear | The sale is written to `realized` and folded into `total_gain`; a test asserts that selling at the market price leaves the total gain unchanged |
| A sale with no recorded cost inflating the realised gain | `realized_gain` and `total_gain` are null, not too large — the same rule the unrealised figure already followed |
| A sale recorded at the market's price by accident | The sell form never pre-fills the amount received; it shows the market value beside the field as a reference only |
| Money moved during the initial entry, when nothing should move | The link is off by default, is a switch the user turns on deliberately, and nothing is applied retroactively |
| A balance that disagrees with its own history | One writer (`app/movements.py`) updates the balance and records the row from the same value, in the same call |
| Money recorded in the wrong cash account | There is only one per currency, and the trade's own currency picks it — nothing to choose, so nothing to choose wrongly |
| A migration quietly rewriting a user's balances | The merge adds the balances up, carries the history across, logs what it merged, and writes a copy of the file beside it first |
| A balance that changed with no line under it | Every path writes one: trades, money in and out, a counted balance, and an opening line for money that predates the history |
| Money in and out becoming income/expense tracking | One signed amount and free text — no category, no month, no total by type, and `test_scope.py` refuses a module named after any of them |
| A delete that prints money | The refund is `net_invested` — what the account actually paid — and a holding never paid for out of cash gives nothing back |
| A browser converting currency on its own | `GET /api/fx/convert`; the client asks, the server converts, and the rate's day and source travel with the answer |
| A trade lost because the cash side could not be filled in | The link never blocks the record: no account, no rate or no cost writes the trade and reports why nothing moved |
| Float rounding on VND (large integers) | Round for display only; VND shown with 0 decimals |

## Order of work

M0 → M1 → M2 → M3 → M4 are strictly sequential (API depends on valuation
depends on FX/prices depends on models). M5 needs only the frozen API shape
from SPEC §6, so its scaffolding starts in parallel with M2/M3. M6 closes both.
