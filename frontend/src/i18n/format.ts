/**
 * Every formatter in the app, and the rules behind them.
 *
 * Three decisions worth stating, because each is a bug avoided:
 *
 * 1. **The locale follows the language, not the currency.** A Vietnamese
 *    reader looking at a dollar figure still wants "1.234,56" — a number is
 *    formatted for the person reading it, not for the currency it is in.
 *
 * 2. **VND is shown with no decimals.** "25.000.000,00 ₫" invents a minor unit
 *    the money does not have in practice.
 *
 * 3. **Money always travels with its currency.** `formatMoney` requires the
 *    currency and has no overload that takes a bare number, so a figure can
 *    never be rendered in a currency it is not in. This is the frontend half of
 *    the rule `app/fx` enforces on the backend.
 *
 * This module is deliberately plain TypeScript with no React in it, so the
 * rules can be tested directly (`frontend/tests/format.test.ts`) rather than
 * through a rendered component.
 */

import type { Currency, Lang } from "../api/types";

/** A missing or unreachable figure. One string, used everywhere. */
export const DASH = "—";

/** Locale used for numbers, dates and sorting, chosen by language. */
const LOCALES: Record<Lang, string> = { vi: "vi-VN", en: "en-US" };

export const LANGUAGES: Lang[] = ["vi", "en"];

/** The currency codes this build can express. */
export const CURRENCIES: Currency[] = ["VND", "USD"];

/** How many decimals a currency is shown with. */
export function decimalsFor(currency: string): number {
  return currency.toUpperCase() === "VND" ? 0 : 2;
}

/**
 * True when a figure is actually present.
 *
 * A predicate rather than a `!missing()` helper: a helper returning `boolean`
 * cannot narrow the argument's type for the compiler, and every formatter
 * below needs the narrowing to hand the value to `Intl`.
 */
export function known(value: number | null | undefined): value is number {
  return value !== null && value !== undefined && !Number.isNaN(value);
}

/**
 * An amount of money, with its currency.
 *
 * `currency` is required. `null` and `NaN` render as the dash, never as "0".
 */
export function formatMoney(
  amount: number | null | undefined,
  currency: string,
  lang: Lang,
): string {
  if (!known(amount)) return DASH;
  return new Intl.NumberFormat(LOCALES[lang], {
    style: "currency",
    currency,
    minimumFractionDigits: decimalsFor(currency),
    maximumFractionDigits: decimalsFor(currency),
  }).format(amount);
}

/** A signed money amount, for a gain or a loss. */
export function formatSignedMoney(
  amount: number | null | undefined,
  currency: string,
  lang: Lang,
): string {
  if (!known(amount)) return DASH;
  const formatted = formatMoney(Math.abs(amount), currency, lang);
  if (amount === 0) return formatted;
  return `${amount > 0 ? "+" : "−"}${formatted}`;
}

/** A plain number — a quantity, a share count — with grouping, no currency. */
export function formatQuantity(
  value: number | null | undefined,
  lang: Lang,
  maxDecimals = 8,
): string {
  if (!known(value)) return DASH;
  return new Intl.NumberFormat(LOCALES[lang], {
    minimumFractionDigits: 0,
    maximumFractionDigits: maxDecimals,
  }).format(value);
}

/** A percentage, with its sign, because a loss and a gain differ. */
export function formatPercent(
  value: number | null | undefined,
  lang: Lang,
  decimals = 2,
): string {
  if (!known(value)) return DASH;
  return new Intl.NumberFormat(LOCALES[lang], {
    style: "percent",
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
    signDisplay: "exceptZero",
  }).format(value / 100);
}

/**
 * A share of a total — an allocation, a weight — as an unsigned percentage.
 *
 * `formatPercent` is for a gain or a loss and prints a `+` on a positive
 * number, which on a slice of a total would read as a movement rather than as a
 * proportion. Those are different quantities with different rules, so they are
 * different formatters rather than one with a flag.
 */
export function formatShare(
  value: number | null | undefined,
  lang: Lang,
  decimals = 1,
): string {
  if (!known(value)) return DASH;
  return new Intl.NumberFormat(LOCALES[lang], {
    style: "percent",
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value / 100);
}

/**
 * `YYYY-MM-DD` is parsed as a calendar date rather than a UTC instant, so a
 * date never shifts by a day for readers west of Greenwich — which is exactly
 * the bug that makes "31/12" read "1/1".
 */
export function parseDate(value: string): Date | null {
  const plain = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (plain) {
    return new Date(Number(plain[1]), Number(plain[2]) - 1, Number(plain[3]));
  }
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

/** An ISO date, or a timestamp, as a date. */
export function formatDate(
  value: string | null | undefined,
  lang: Lang,
): string {
  if (!value) return DASH;
  const date = parseDate(value);
  if (date === null) return value;
  return new Intl.DateTimeFormat(LOCALES[lang], {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(date);
}

/** The same, with the time of day, for "fetched at". */
export function formatDateTime(
  value: string | null | undefined,
  lang: Lang,
): string {
  if (!value) return DASH;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(LOCALES[lang], {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

/** A short day/month label, for chart axes. */
export function formatMonthDay(value: string, lang: Lang): string {
  const date = parseDate(value);
  if (date === null) return value;
  return new Intl.DateTimeFormat(LOCALES[lang], {
    day: "2-digit",
    month: "2-digit",
  }).format(date);
}

/**
 * A rate, shown with enough precision to be useful.
 *
 * Up to eight decimals, because a VND-per-USD rate inverted is 0.000038…: at
 * six it prints as 0,000038 and two different days read as the same number.
 * Eight is also short enough for a table cell.
 */
export function formatRate(
  value: number | null | undefined,
  lang: Lang,
): string {
  if (!known(value)) return DASH;
  return new Intl.NumberFormat(LOCALES[lang], {
    minimumFractionDigits: 2,
    maximumFractionDigits: 8,
  }).format(value);
}
