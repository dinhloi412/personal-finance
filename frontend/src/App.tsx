/**
 * The shell: providers, navigation, and the page switch.
 *
 * The providers are nested this way round on purpose. `AppProvider` learns the
 * stored language from the server and hands it up to `I18nProvider`, so the
 * interface is drawn in the user's language from the first render that has any
 * text in it — rather than being drawn in Vietnamese and then swapping.
 *
 * Routing is a `useState` and a `pushState`, not a router library: there are
 * five pages, no nested routes, and no data loading tied to a URL. A router
 * here would be a dependency to satisfy a problem this app does not have.
 */

import { useCallback, useEffect, useState } from "react";

import { AppProvider, useApp } from "./state/AppContext";
import { I18nProvider, formatMoney, useI18n } from "./i18n";
import type { Lang } from "./api/types";
import { Button, Notice, Spinner } from "./components/ui";
import { Cash } from "./views/Cash";
import { Dashboard } from "./views/Dashboard";
import { Holdings } from "./views/Holdings";
import { Market } from "./views/Market";
import { Savings } from "./views/Savings";
import { Settings } from "./views/Settings";

type Route =
  | "dashboard"
  | "holdings"
  | "cash"
  | "savings"
  | "market"
  | "settings";

/** The order the pages are listed in, which is the order they are used in:
 * what the market prices, what the bank holds, what is left over, then the
 * reference pages. */
const ROUTES: Route[] = [
  "dashboard",
  "holdings",
  "cash",
  "savings",
  "market",
  "settings",
];

const PATHS: Record<Route, string> = {
  dashboard: "/",
  holdings: "/holdings",
  cash: "/cash",
  savings: "/savings",
  market: "/market",
  settings: "/settings",
};

function routeFromLocation(): Route {
  const path = globalThis.location?.pathname ?? "/";
  const found = ROUTES.find((route) => PATHS[route] === path);
  return found ?? "dashboard";
}

export function App() {
  // Held here rather than inside the provider so that the provider's discovery
  // of the stored language can be handed straight to the i18n layer.
  const [lang, setLang] = useState<Lang>(
    () => (globalThis.localStorage?.getItem("sotaisan.lang") as Lang) ?? "vi",
  );

  return (
    <I18nProvider initial={lang}>
      <AppProvider onLanguage={setLang}>
        <Shell />
      </AppProvider>
    </I18nProvider>
  );
}

/**
 * What the last refresh did.
 *
 * The refresh button lives in the header, which is the right place for it and
 * the wrong place to show a per-symbol failure — a price feed that answered
 * for nineteen symbols and not the twentieth is not an error page, it is one
 * row of news. So the report is kept in the context and shown here, where
 * there is room for it and where it can be dismissed.
 */
function RefreshReport() {
  const { t } = useI18n();
  const app = useApp();
  const report = app.lastRefresh;

  if (report === null) return null;

  const failures = report.prices.failed;
  const rateFailed = !report.fx.ok;

  if (failures.length === 0 && !rateFailed) {
    return (
      <Notice tone="info" onDismiss={app.clearRefresh}>
        {t("dash.refresh_done", { count: report.prices.refreshed.length })}
      </Notice>
    );
  }

  return (
    <Notice
      tone={failures.length > 0 ? "warning" : "error"}
      title={
        failures.length > 0
          ? t("dash.refresh_failed", {
              list: failures.map((failure) => failure.symbol).join(", "),
            })
          : t("market.refresh_error")
      }
      onDismiss={app.clearRefresh}
    >
      <ul className="space-y-1">
        {failures.map((failure) => (
          <li key={failure.symbol} className="flex flex-wrap items-baseline gap-x-2">
            <span className="font-medium">{failure.symbol}</span>
            <span>{failure.error}</span>
          </li>
        ))}
        {rateFailed && <li>{report.fx.error ?? t("market.refresh_error")}</li>}
      </ul>
    </Notice>
  );
}

function Shell() {
  const { t } = useI18n();
  const app = useApp();
  const [route, setRoute] = useState<Route>(routeFromLocation);

  // A deep link (or a refresh on /cash) must land on that page, and the back
  // button must work, which means listening to the history as well as pushing.
  useEffect(() => {
    const onPop = () => setRoute(routeFromLocation());
    globalThis.addEventListener("popstate", onPop);
    return () => globalThis.removeEventListener("popstate", onPop);
  }, []);

  const go = useCallback((next: Route) => {
    setRoute(next);
    globalThis.history?.pushState(null, "", PATHS[next]);
  }, []);

  const total = app.portfolio?.total ?? null;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-3 px-4 py-3">
          <div className="flex items-baseline gap-2">
            <span className="text-base font-semibold tracking-tight">
              {t("app.name")}
            </span>
            <span className="hidden text-xs text-slate-500 sm:inline">
              {t("app.tagline")}
            </span>
          </div>

          <nav className="order-3 flex flex-wrap gap-1 sm:order-2">
            {ROUTES.map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => go(item)}
                className={`rounded-lg px-2.5 py-1.5 text-sm font-medium transition-colors ${
                  route === item
                    ? "bg-slate-900 text-white"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                }`}
              >
                {t(`nav.${item}` as const)}
              </button>
            ))}
          </nav>

          <div className="order-2 ml-auto flex items-center gap-3 sm:order-3">
            <span className="text-right">
              <span className="block text-xs text-slate-500">{t("dash.total")}</span>
              <span className="block text-sm font-semibold tabular-nums">
                {formatMoney(total, app.baseCurrency, app.lang)}
              </span>
            </span>
            <Button
              size="sm"
              onClick={() => {
                void app.refreshAll();
              }}
            >
              {t("action.refresh")}
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-4 px-4 py-6">
        {app.error && (
          <Notice tone="error" title={t("state.error")}>
            {app.error}
          </Notice>
        )}

        <RefreshReport />

        {app.loading && app.portfolio === null ? (
          <Spinner label={t("state.loading")} />
        ) : (
          <>
            {route === "dashboard" && <Dashboard />}
            {route === "holdings" && <Holdings />}
            {route === "cash" && <Cash />}
            {route === "savings" && <Savings />}
            {route === "market" && <Market />}
            {route === "settings" && <Settings />}
          </>
        )}
      </main>

      <footer className="mx-auto max-w-6xl px-4 pb-10 text-xs text-slate-500">
        {t("app.offline_note")}
      </footer>
    </div>
  );
}
