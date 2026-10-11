/**
 * The language provider, `t()`, and the re-exported formatters.
 *
 * There is no i18n library here on purpose. Two languages, one flat key space,
 * and a `Dict` interface that makes a missing key a compile error rather than a
 * runtime fallback to English — that is the whole feature set needed.
 *
 * The formatters live in `./format` (plain TypeScript, no React) so they can be
 * tested directly; they are re-exported here so a view imports from one place.
 */

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";
import type { ReactNode } from "react";

import type { Lang } from "../api/types";
import { en } from "./en";
import { vi } from "./vi";
import type { TranslationKey, Vars } from "./types";

export * from "./format";
export { en, vi };
export type { Dict, TranslationKey, Vars } from "./types";

const DICTS: Record<Lang, typeof vi> = { vi, en };

const STORAGE_KEY = "sotaisan.lang";

interface I18nValue {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: (key: TranslationKey, vars?: Vars) => string;
}

const I18nContext = createContext<I18nValue | null>(null);

export function storedLanguage(): Lang {
  const stored = globalThis.localStorage?.getItem(STORAGE_KEY);
  return stored === "en" || stored === "vi" ? stored : "vi";
}

/** Fill `{name}` placeholders. An unknown placeholder is left visible. */
function interpolate(text: string, vars?: Vars): string {
  if (!vars) return text;
  return text.replace(/\{(\w+)\}/g, (whole, name: string) => {
    const value = vars[name];
    return value === undefined ? whole : String(value);
  });
}

export function I18nProvider({
  children,
  initial,
}: {
  children: ReactNode;
  /** The language the server last knew about, used for the first paint. */
  initial?: Lang;
}) {
  const [lang, setLangState] = useState<Lang>(() => initial ?? storedLanguage());

  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    // Mirrored locally so the next first paint is already in the right
    // language, before the settings request has answered.
    globalThis.localStorage?.setItem(STORAGE_KEY, next);
  }, []);

  const value = useMemo<I18nValue>(() => {
    const dict = DICTS[lang];
    return {
      lang,
      setLang,
      // The English fallback is for a key that exists in the interface type but
      // somehow not in the dictionary at runtime; it is not a substitute for
      // the compile-time check the `Dict` interface provides.
      t: (key, vars) => interpolate(dict[key] ?? en[key] ?? key, vars),
    };
  }, [lang, setLang]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const value = useContext(I18nContext);
  if (value === null) {
    throw new Error("useI18n must be used inside an I18nProvider");
  }
  return value;
}

/** The common case: just the translator. */
export function useT(): I18nValue["t"] {
  return useI18n().t;
}

export function useLang(): Lang {
  return useI18n().lang;
}
