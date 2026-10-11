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
/** Everything that makes up the net worth, including the two kinds with no
 * market behind them: cash, which the user counts, and a term deposit, whose
 * value is computed from its own terms. */
export type AssetKind = MarketKind | "cash" | "deposit" | "gold";
/** The weights gold is held in. A lượng is ten chỉ, by definition. */
export type GoldUnit = "chi" | "luong" | "gram" | "ounce";
/** Which of a goldshop's two prices a holding is valued at. The shop buys at
 * one and sells at the other, and the gap between them is real money. */
export type GoldPricing = "buy" | "sell";
/** The only interest behaviour implemented, so the type says so rather than
 * offering a choice that would do nothing. */
export type InterestMode = "at_maturity";
export type Lang = "vi" | "en";
/** What can move money in or out of a cash balance. `cash` is the odd one: not
 * a holding, but the user putting money in or taking it out themselves. */
export type SubjectKind = "asset" | "gold" | "deposit" | "cash";
/** Why a cash movement happened. Structured rather than a sentence, because
 * the sentence has to exist in two languages. */
export type FlowAction =
  | "buy"
  | "sell"
  | "open"
  | "close"
  | "adjust"
  | "refund"
  | "in"
  | "out";
/** Why the cash side of a trade did nothing. */
export type SkipCode =
  | "link_off"
  | "no_amount"
  | "no_account"
  | "no_rate"
  | "nothing_paid";

/** The cash side of a trade, as the client asks for it.
 *
 * There is no account to choose: cash is one pot per currency and the pot is
 * the trade's own currency (`app.cash`).
 *
 * `cash_amount` is optional by design: with the cash link off it is ignored,
 * and with it on it overrides what the app would do on its own. Omitting it
 * means "move what this trade is worth" — which, the pot being in the trade's
 * currency, is the trade's own number; sending it means "this is what actually
 * left the account", the one figure only the user has. */
export interface CashMoveRequest {
  /** Positive, in the pot's currency: the direction comes from the trade. */
  cash_amount?: number | null;
}

/** What the cash side actually did, or why it did nothing. */
export interface CashMoveOut extends CashMoveRequest {
  moved: boolean;
  skipped?: SkipCode | null;
  movement_id?: number | null;
  /** The pot it moved, which is always the trade's own currency. */
  account_id?: number | null;
  account_name?: string | null;
  /** Signed, in `currency`: negative is money out of the account. */
  amount?: number | null;
  currency?: string | null;
  /** The account's balance after the movement. */
  balance?: number | null;
}

/** One movement of a cash balance, and what caused it. */
export interface CashMovement {
  id: number;
  account_id: number;
  subject: SubjectKind;
  action: FlowAction;
  /** The holding's id at the time, null once it is gone. */
  holding_id: number | null;
  symbol: string | null;
  name: string;
  /** Signed: negative is money out of the account. */
  amount: number;
  currency: string;
  /** Units of `currency` per 1 of the holding's, when the two differed. */
  rate: number | null;
  occurred_on: string;
  note: string | null;
}

/** What a delete did besides removing the row. */
export interface DeleteResult {
  removed_id: number;
  cash: CashMoveOut;
}

/** Why a figure is missing. Rendered as an explanation, never as a dash. */
export type UnpricedReason =
  | "unpriced"
  | "not_convertible"
  | "no_quantity"
  | "no_cost"
  /** Gold only: the product line this holding follows is no longer in the
   * goldshop's price list. */
  | "no_shop_price"
  /** Gold only: the goldshop's price list could not be fetched at all. */
  | "price_list_unreachable";

export interface Settings {
  base_currency: Currency;
  language: Lang;
  /** Whether trades move money in and out of a cash account. Off by default. */
  cash_linked: boolean;
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
  /** What the cash side of this trade did. */
  cash: CashMoveOut | null;
}

export interface AssetInput extends CashMoveRequest {
  symbol: string;
  kind: MarketKind;
  name?: string | null;
  quantity: number;
  cost_basis?: number | null;
  currency: Currency;
  note?: string | null;
}

export type AssetPatch = Partial<AssetInput>;

/** Selling part or all of a position.
 *
 * `proceeds` is the total received, not a price per unit — the same rule as
 * `cost_basis`, and for the same reason. Its currency is not here: money
 * received for a position is in the market's currency for that symbol, which
 * the server knows and the form shows but does not ask about. */
export interface AssetSale extends CashMoveRequest {
  quantity: number;
  proceeds: number;
  /** Defaults to today, server-side. */
  sold_on?: string;
  note?: string | null;
}

/** One closed position: what it sold for against what it released.
 *
 * `cost_removed` is the *proportional* part of the position's cost basis, and
 * null when the position never had one recorded — which is why `gain` can be
 * null on a sale that clearly made money. */
export interface Realized {
  id: number;
  symbol: string;
  name: string;
  kind: MarketKind;
  quantity: number;
  /** The currency the cost was recorded in. */
  currency: Currency;
  sold_on: string;
  note: string | null;
  proceeds: number;
  /** The market's currency, which may be one this app cannot convert. */
  proceeds_currency: string;
  cost_removed: number | null;
  proceeds_base: number | null;
  cost_base: number | null;
  gain: number | null;
  gain_pct: number | null;
  reason: UnpricedReason | null;
  cash: CashMoveOut | null;
}

export interface CashAccount {
  id: number;
  name: string;
  currency: Currency;
  balance: number;
  balance_at: string;
  note: string | null;
  value_base: number | null;
  reason: UnpricedReason | null;
  /** The movement a balance edit recorded, when there was one. */
  cash: CashMoveOut | null;
}

/** Money the user says went into a balance, or came out of it.
 *
 * The amount is positive and the direction is spelled out: a form asking for
 * "-500000" to mean a withdrawal is a form that will one day record one the
 * wrong way round. The reason is free text — a salary, a bill, a gift — and
 * never a category, because a category is the first step to a budget. */
export interface CashEntry {
  amount: number;
  direction: "in" | "out";
  /** Defaults to today, server-side. */
  occurred_on?: string;
  note?: string | null;
}

export interface CashEntryResult {
  account: CashAccount;
  cash: CashMoveOut;
}

/** One entry of the cash history, as the history card reads it. */

/** An edit to one pot: its label, its balance, its note. The currency is not
 * here — it is the pot's identity, and there are exactly two. */
export interface CashPatch {
  name?: string;
  balance?: number;
  note?: string | null;
}

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

export interface Deposit {
  id: number;
  name: string;
  currency: Currency;
  principal: number;
  /** Percent per year, as the contract quotes it: 6.5 means 6.5%. */
  annual_rate: number;
  start_date: string;
  /** Null is a demand deposit (không kỳ hạn): no end, keeps accruing. */
  maturity_date: string | null;
  interest_mode: InterestMode;
  note: string | null;

  /** The day the interest was computed for. */
  as_of: string;
  days_accrued: number;
  interest_accrued: number;
  /** principal + interest_accrued, in the deposit's own currency. */
  value: number;
  /** Interest has stopped: the money needs a decision. */
  matured: boolean;
  days_remaining: number | null;
  /** principal + full-term interest. */
  value_at_maturity: number;

  value_base: number | null;
  interest_base: number | null;
  reason: UnpricedReason | null;
  cash: CashMoveOut | null;
}

export interface DepositInput extends CashMoveRequest {
  name: string;
  currency: Currency;
  principal: number;
  annual_rate: number;
  start_date: string;
  maturity_date?: string | null;
  interest_mode?: InterestMode;
  note?: string | null;
}

export type DepositPatch = Partial<DepositInput>;

export interface DepositRoll {
  principal?: number | null;
  annual_rate?: number | null;
  start_date?: string | null;
  maturity_date?: string | null;
  note?: string | null;
}

export interface DepositWithdraw extends CashMoveRequest {
  /** What the bank actually paid, when that differs from the arithmetic. */
  balance?: number | null;
}

export interface DepositWithdrawn {
  closed_deposit_id: number;
  /** The account the money landed in, after it landed. */
  account: CashAccount;
  amount: number;
  cash: CashMoveOut;
}

export interface GoldProduct {
  key: string;
  name: string;
  /** Price for ONE unit (a chỉ) at which the shop buys. */
  buy: number;
  /** Price for ONE unit at which the shop sells. */
  sell: number;
  unit: string;
  /** The shop's own timestamp, as text, exactly as it published it. */
  updated_at: string;
  updated_on: string;
}

export interface GoldProducts {
  products: GoldProduct[];
  /** True when the shop could not be reached: an empty list would otherwise
   * read as "no gold exists", which is a different fact. */
  degraded: boolean;
  error: string | null;
  source: string;
}

export interface GoldHolding {
  id: number;
  name: string;
  currency: Currency;
  quantity: number;
  unit: GoldUnit;
  pricing: GoldPricing;
  note: string | null;

  product_key: string;
  product_name: string | null;
  /** The shop's figure for its own product line, in VND. */
  shop_price: number | null;
  /** That figure expressed for ONE unit of the unit held, in VND. */
  price: number | null;
  price_as_of: string | null;
  price_source: string | null;

  value: number | null;
  value_base: number | null;
  cost_basis: number | null;
  reason: UnpricedReason | null;
  cash: CashMoveOut | null;
}

export interface GoldInput extends CashMoveRequest {
  name: string;
  currency: Currency;
  quantity: number;
  unit: GoldUnit;
  product_key: string;
  pricing: GoldPricing;
  cost_basis?: number | null;
  note?: string | null;
}

export type GoldPatch = Partial<GoldInput>;

export interface Portfolio {
  base_currency: Currency;
  total: number;
  market_value: number;
  cash_value: number;
  deposit_value: number;
  gold_value: number;
  cost_base: number | null;
  gain: number | null;
  gain_pct: number | null;
  /** Closed positions, newest first, and the figures built from them. */
  realized: Realized[];
  /** Null when any sale is missing its cost — a total that would be too big. */
  realized_gain: number | null;
  realized_cost_base: number | null;
  realized_count: number;
  /** Unrealised + realised. Null when either side is unknown. */
  total_gain: number | null;
  total_gain_pct: number | null;
  /** Every cash movement, newest first. */
  movements: CashMovement[];
  assets: Asset[];
  cash: CashAccount[];
  deposits: Deposit[];
  gold: GoldHolding[];
  by_kind: KindTotal[];
  by_currency: CurrencyTotal[];
  unconverted: Unconverted[];
  rates: RateUsed[];
  counts: {
    assets: number;
    cash: number;
    deposits: number;
    gold: number;
    unconverted: number;
  };
}

export interface ValuationPoint {
  as_of: string;
  base_currency: string;
  total: number;
  market_value: number;
  cash_value: number;
  deposit_value: number;
  gold_value: number;
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

/** Where a price came from. A market close and a fund's NAV are not the same
 * kind of fact, so the interface says which one it is showing. */
export type PriceSource = "market" | "fund" | string;

export interface PriceRow {
  symbol: string;
  price: number;
  currency: string | null;
  as_of: string;
  fetched_at: string;
  error: string | null;
  source: PriceSource;
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
