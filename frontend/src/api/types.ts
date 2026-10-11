/**
 * The shapes the API answers with, written by hand.
 *
 * These mirror `backend/app/schemas.py` field for field. The pair is meant to
 * be read side by side: if a field is renamed on one side and not the other,
 * TypeScript fails the build, which is the whole point of not generating them.
 *
 * Two things to notice in the types themselves:
 *
 * - `number | null` is everywhere a figure can be unknown. It is never `0`.
 *   Zero means "none"; null means "we do not know", and the difference is the
 *   difference between a tracker and a guess.
 * - `Currency` is two strings. A third currency cannot be expressed, so it
 *   cannot be sent, stored, or added to a total by accident.
 */

export type Currency = "VND" | "USD";
export type MarketKind = "stock" | "fund" | "crypto";
export type AssetKind = MarketKind | "cash";
export type Lang = "vi" | "en";

/** Why a figure is missing. Rendered as an explanation, never as a dash. */
export type UnpricedReason =
  | "unpriced"
  | "not_convertible"
  | "no_quantity"
  | "no_cost";

export interface Settings {
  base_currency: Currency;
  language: Lang;
  supported_currencies: Currency[];
  supported_kinds: AssetKind[];
  supported_languages: Lang[];
  database_path: string;
  version: string;
}

export interface Asset {
  id: number;
  symbol: string;
  name: string;
  kind: MarketKind;
  quantity: number;
  currency: Currency;
  cost_basis: number | null;
  note: string | null;
  price: number | null;
  price_currency: string | null;
  price_as_of: string | null;
  price_fetched_at: string | null;
  value: number | null;
  value_base: number | null;
  cost_base: number | null;
  gain: number | null;
  gain_pct: number | null;
  reason: UnpricedReason | null;
}

export interface AssetInput {
  symbol: string;
  kind: MarketKind;
  name?: string | null;
  quantity: number;
  cost_basis?: number | null;
  currency: Currency;
  note?: string | null;
}

export type AssetPatch = Partial<AssetInput>;

export interface CashAccount {
  id: number;
  name: string;
  currency: Currency;
  balance: number;
  balance_at: string;
  note: string | null;
  value_base: number | null;
  reason: UnpricedReason | null;
}

export interface CashInput {
  name: string;
  currency: Currency;
  balance: number;
  note?: string | null;
}

export type CashPatch = Partial<CashInput>;

export interface KindTotal {
  kind: AssetKind;
  value: number;
  count: number;
}

export interface CurrencyTotal {
  currency: string;
  /** In that currency. NOT comparable with another row's `amount`. */
  amount: number;
  /** The same money in the base currency. This is the comparable one. */
  value_base: number;
  decimals: number;
}

export interface RateUsed {
  currency: string;
  rate: number;
  as_of: string;
  source: string;
  stale: boolean;
}

export interface Unconverted {
  kind: string;
  id: number;
  label: string;
  reason: UnpricedReason | null;
}

export interface Portfolio {
  base_currency: Currency;
  total: number;
  market_value: number;
  cash_value: number;
  cost_base: number | null;
  gain: number | null;
  gain_pct: number | null;
  assets: Asset[];
  cash: CashAccount[];
  by_kind: KindTotal[];
  by_currency: CurrencyTotal[];
  unconverted: Unconverted[];
  rates: RateUsed[];
  counts: { assets: number; cash: number; unconverted: number };
}

export interface ValuationPoint {
  as_of: string;
  base_currency: string;
  total: number;
  market_value: number;
  cash_value: number;
  cost_value: number | null;
  unconverted_count: number;
}

export interface History {
  base_currency: Currency;
  points: ValuationPoint[];
}

export interface Suggestion {
  symbol: string;
  name: string;
  kind: string | null;
  exchange: string | null;
  currency: string | null;
  score: number;
}

export interface SearchResult {
  query: string;
  suggestions: Suggestion[];
  /** True when the feed could not be reached. Typing a symbol still works. */
  degraded: boolean;
}

export interface PriceRow {
  symbol: string;
  price: number;
  currency: string | null;
  as_of: string;
  fetched_at: string;
  error: string | null;
}

export interface FxRow {
  base: string;
  currency: string;
  as_of: string;
  rate: number;
  source: string;
  fetched_at: string;
}

export interface Market {
  base_currency: Currency;
  prices: PriceRow[];
  rates: FxRow[];
}

export interface RefreshFailure {
  symbol: string;
  error: string;
}

export interface PriceRefresh {
  ok: boolean;
  refreshed: string[];
  failed: RefreshFailure[];
  asked: number;
}

export interface FxBaseReport {
  ok: boolean;
  error: string | null;
  stored: string[];
  as_of: string;
}

export interface FxRefresh {
  ok: boolean;
  error: string | null;
  stored: string[];
  as_of: string;
  bases: Record<string, FxBaseReport>;
}

export interface RefreshAll {
  prices: PriceRefresh;
  fx: FxRefresh;
}
