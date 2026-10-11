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
| M6 tests, demo, run script | done | **104 backend tests pass**, `app/seed.py`, `start.sh` |
| M7 verify | done | live run against Yahoo + the FX feed on port 8010; `scripts/acceptance.sh` green |

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

Three things were found by verifying rather than by building, and each changed
the design:

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
| Float rounding on VND (large integers) | Round for display only; VND shown with 0 decimals |

## Order of work

M0 → M1 → M2 → M3 → M4 are strictly sequential (API depends on valuation
depends on FX/prices depends on models). M5 needs only the frozen API shape
from SPEC §6, so its scaffolding starts in parallel with M2/M3. M6 closes both.
