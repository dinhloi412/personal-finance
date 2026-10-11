/**
 * The application's shared state: settings, the valued portfolio, and the one
 * `refresh()` every mutation calls.
 *
 * There is one source of truth here on purpose. A view that fetched its own
 * copy of the portfolio would show a stale total the moment another view
 * changed something, and the two would disagree about the same money. So every
 * write goes through this context, and every write ends in a refresh.
 *
 * The provider also owns the two things that are global by nature: the base
 * currency (which changes what every number means) and the language.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { ReactNode } from "react";

import * as api from "../api/client";
import { ApiError } from "../api/client";
import type {
  Currency,
  History,
  Lang,
  Portfolio,
  RefreshAll,
  Settings,
} from "../api/types";

interface AppValue {
  /** Null until the first load has answered. */
  settings: Settings | null;
  portfolio: Portfolio | null;
  history: History | null;
  loading: boolean;
  /** A human-readable message for the last failure, or null. */
  error: string | null;
  /** What the last refresh did, per symbol. Null until one has run. */
  lastRefresh: RefreshAll | null;
  /** Forget the last refresh report, once it has been read. */
  clearRefresh: () => void;
  baseCurrency: Currency;
  lang: Lang;

  /** Re-read everything. Called after every mutation. */
  refresh: () => Promise<void>;
  /** Fetch new prices and rates, then re-read everything. */
  refreshAll: () => Promise<RefreshAll>;
  /** Change the base currency and re-read. */
  setBaseCurrency: (currency: Currency) => Promise<void>;
  /** Change the language: stored on the server and applied immediately. */
  setLanguage: (lang: Lang) => Promise<void>;
  /** Record today's valuation. */
  snapshot: () => Promise<void>;
}

const AppContext = createContext<AppValue | null>(null);

function messageOf(cause: unknown): string {
  if (cause instanceof ApiError) return cause.message;
  if (cause instanceof Error) return cause.message;
  return String(cause);
}

export function AppProvider({
  children,
  onLanguage,
}: {
  children: ReactNode;
  /** Lets the provider tell the i18n layer which language to apply. */
  onLanguage?: (lang: Lang) => void;
}) {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [history, setHistory] = useState<History | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<RefreshAll | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      // One round of requests, not three sequential ones: nothing here depends
      // on anything else in the group.
      const [nextSettings, nextPortfolio, nextHistory] = await Promise.all([
        api.getSettings(),
        api.getPortfolio(),
        api.getHistory(),
      ]);
      setSettings(nextSettings);
      setPortfolio(nextPortfolio);
      setHistory(nextHistory);
      setError(null);
      onLanguage?.(nextSettings.language);
    } catch (cause) {
      setError(messageOf(cause));
    } finally {
      setLoading(false);
    }
  }, [onLanguage]);

  useEffect(() => {
    void load();
  }, [load]);

  const refreshAll = useCallback(async () => {
    try {
      const report = await api.refreshAll();
      // Kept rather than returned only: the button that starts a refresh lives
      // in the header, which has nowhere to render a per-symbol failure, and a
      // refresh that silently failed for one symbol is the kind of thing a
      // price tracker must not do.
      setLastRefresh(report);
      await load();
      return report;
    } catch (cause) {
      setError(messageOf(cause));
      throw cause;
    }
  }, [load]);

  const clearRefresh = useCallback(() => setLastRefresh(null), []);

  const setBaseCurrency = useCallback(
    async (currency: Currency) => {
      try {
        const next = await api.updateSettings({ base_currency: currency });
        setSettings(next);
        await load();
      } catch (cause) {
        setError(messageOf(cause));
        throw cause;
      }
    },
    [load],
  );

  const setLanguage = useCallback(
    async (lang: Lang) => {
      // Applied before the request so the interface answers the click at once;
      // the server copy is what survives a restart.
      onLanguage?.(lang);
      try {
        const next = await api.updateSettings({ language: lang });
        setSettings(next);
      } catch (cause) {
        setError(messageOf(cause));
        throw cause;
      }
    },
    [onLanguage],
  );

  const snapshot = useCallback(async () => {
    try {
      await api.writeSnapshot();
      setHistory(await api.getHistory());
    } catch (cause) {
      setError(messageOf(cause));
      throw cause;
    }
  }, []);

  const value = useMemo<AppValue>(
    () => ({
      settings,
      portfolio,
      history,
      loading,
      error,
      baseCurrency: settings?.base_currency ?? "VND",
      lang: settings?.language ?? "vi",
      lastRefresh,
      clearRefresh,
      refresh: load,
      refreshAll,
      setBaseCurrency,
      setLanguage,
      snapshot,
    }),
    [
      settings,
      portfolio,
      history,
      loading,
      error,
      lastRefresh,
      clearRefresh,
      load,
      refreshAll,
      setBaseCurrency,
      setLanguage,
      snapshot,
    ],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppValue {
  const value = useContext(AppContext);
  if (value === null) {
    throw new Error("useApp must be used inside an AppProvider");
  }
  return value;
}
