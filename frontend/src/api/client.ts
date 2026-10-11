/**
 * One function per endpoint, and one place where a failure is turned into a
 * message.
 *
 * Paths are RELATIVE (`/api/...`) on purpose: the same code works behind the
 * Vite dev proxy and in production, where FastAPI serves this bundle itself.
 * An absolute URL would need a different value in development than in
 * production, which is exactly the kind of setting that is wrong on someone
 * else's machine and nowhere else.
 */

import type {
  Asset,
  AssetInput,
  AssetPatch,
  AssetSale,
  CashAccount,
  CashEntry,
  CashEntryResult,
  CashPatch,
  DeleteResult,
  Deposit,
  DepositInput,
  DepositPatch,
  DepositRoll,
  DepositWithdraw,
  DepositWithdrawn,
  FxRefresh,
  GoldHolding,
  GoldInput,
  GoldPatch,
  GoldProducts,
  History,
  Market,
  Portfolio,
  PriceRefresh,
  Realized,
  RefreshAll,
  SearchResult,
  Settings,
} from "./types";

/** A failed request, carrying the status and whatever the server said. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(
  path: string,
  init: RequestInit & { json?: unknown } = {},
): Promise<T> {
  const { json, ...rest } = init;
  const response = await fetch(`/api${path}`, {
    ...rest,
    headers:
      json === undefined
        ? rest.headers
        : { "Content-Type": "application/json", ...(rest.headers ?? {}) },
    body: json === undefined ? rest.body : JSON.stringify(json),
  });

  if (!response.ok) {
    throw new ApiError(response.status, await readError(response));
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

/**
 * FastAPI's own error body is `{detail: ...}`, where `detail` is a string for
 * a refusal we wrote and a list of field errors for a validation failure.
 * Both are turned into one readable sentence, because the alternative is the
 * user reading "[object Object]".
 */
async function readError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    const detail = body?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item: { loc?: unknown[]; msg?: string }) => {
          const field = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : "";
          return field ? `${field}: ${item.msg ?? ""}` : (item.msg ?? "");
        })
        .join("; ");
    }
  } catch {
    // The body was not JSON; the status line is all we have.
  }
  return `${response.status} ${response.statusText}`;
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

export const getSettings = () => request<Settings>("/settings");

export const updateSettings = (patch: {
  base_currency?: string;
  language?: string;
  /** Turning this on makes every later trade move money. */
  cash_linked?: boolean;
}) => request<Settings>("/settings", { method: "PATCH", json: patch });

/**
 * Delete every position, cash balance and recorded point.
 *
 * Settings, cached prices and cached rates survive — they are not the user's
 * records, and throwing away a rate would leave a fresh start unable to
 * convert anything. The caller must confirm first; this function does not.
 */
export const wipeData = () =>
  request<{ removed: Record<string, number> }>("/settings/wipe", {
    method: "POST",
  });

// ---------------------------------------------------------------------------
// Positions
// ---------------------------------------------------------------------------

export const listAssets = () => request<Asset[]>("/assets");

export const createAsset = (input: AssetInput) =>
  request<Asset>("/assets", { method: "POST", json: input });

export const updateAsset = (id: number, patch: AssetPatch) =>
  request<Asset>(`/assets/${id}`, { method: "PATCH", json: patch });

/** Deleting a position may also give money back, so it answers with what it
 * did rather than with an empty body. */
export const deleteAsset = (id: number) =>
  request<DeleteResult>(`/assets/${id}`, { method: "DELETE" });

export const priceAsset = (id: number) =>
  request<Asset>(`/assets/${id}/price`, { method: "POST" });

/**
 * Sell part or all of a position.
 *
 * The gain is computed by the server from the position's cost basis and this
 * one amount — never from the current price, which is what the position would
 * be worth if it had not been sold.
 */
export const sellAsset = (id: number, body: AssetSale) =>
  request<Realized>(`/assets/${id}/sell`, { method: "POST", json: body });

// ---------------------------------------------------------------------------
// Sold positions
// ---------------------------------------------------------------------------

export const listRealized = () => request<Realized[]>("/realized");

/** Forget one recorded sale. The position it closed is not restored. */
export const deleteRealized = (id: number) =>
  request<void>(`/realized/${id}`, { method: "DELETE" });

// ---------------------------------------------------------------------------
// Cash: one pot per currency
// ---------------------------------------------------------------------------

export const listCash = () => request<CashAccount[]>("/cash");

/** Edit a pot: its balance (the manual update), its label, its note. */
export const updateCash = (id: number, patch: CashPatch) =>
  request<CashAccount>(`/cash/${id}`, { method: "PATCH", json: patch });

/** Record money going into a balance, or coming out of it. */
export const cashEntry = (id: number, body: CashEntry) =>
  request<CashEntryResult>(`/cash/${id}/entry`, { method: "POST", json: body });

// ---------------------------------------------------------------------------
// Term deposits (savings)
// ---------------------------------------------------------------------------

export const listDeposits = (matured?: boolean) => {
  const query = matured === undefined ? "" : `?matured=${matured}`;
  return request<Deposit[]>(`/deposits${query}`);
};

export const createDeposit = (input: DepositInput) =>
  request<Deposit>("/deposits", { method: "POST", json: input });

export const updateDeposit = (id: number, patch: DepositPatch) =>
  request<Deposit>(`/deposits/${id}`, { method: "PATCH", json: patch });

export const deleteDeposit = (id: number) =>
  request<DeleteResult>(`/deposits/${id}`, { method: "DELETE" });

/** The value from today to maturity, computed by the same arithmetic. */
export const depositSchedule = (id: number) =>
  request<Deposit[]>(`/deposits/${id}/schedule`);

/** Roll a matured deposit into a new term: interest becomes principal. */
export const rollDeposit = (id: number, body: DepositRoll = {}) =>
  request<Deposit>(`/deposits/${id}/roll`, { method: "POST", json: body });

/** Close a deposit and record the proceeds as cash, in one request. */
export const withdrawDeposit = (id: number, body: DepositWithdraw = {}) =>
  request<DepositWithdrawn>(`/deposits/${id}/withdraw`, { method: "POST", json: body });

// ---------------------------------------------------------------------------
// Gold (Vietnamese, priced by the shop)
// ---------------------------------------------------------------------------

/** Every line the goldshop publishes, normalised to a price per chỉ. */
export const listGoldProducts = (query?: string, fresh = false) => {
  const params = new URLSearchParams();
  if (query) params.set("q", query);
  if (fresh) params.set("fresh", "true");
  const suffix = params.toString();
  return request<GoldProducts>(`/gold/products${suffix ? `?${suffix}` : ""}`);
};

export const listGold = () => request<GoldHolding[]>("/gold");

export const createGold = (input: GoldInput) =>
  request<GoldHolding>("/gold", { method: "POST", json: input });

export const updateGold = (id: number, patch: GoldPatch) =>
  request<GoldHolding>(`/gold/${id}`, { method: "PATCH", json: patch });

export const deleteGold = (id: number) =>
  request<DeleteResult>(`/gold/${id}`, { method: "DELETE" });

// ---------------------------------------------------------------------------
// The portfolio
// ---------------------------------------------------------------------------

export const getPortfolio = () => request<Portfolio>("/portfolio");

export const getHistory = () => request<History>("/portfolio/history");

export const writeSnapshot = () =>
  request<History["points"][number]>("/portfolio/snapshot", { method: "POST" });

// ---------------------------------------------------------------------------
// Feeds
// ---------------------------------------------------------------------------

export const searchSymbols = (query: string, kind?: string) => {
  const params = new URLSearchParams({ q: query });
  if (kind) params.set("kind", kind);
  return request<SearchResult>(`/market/search?${params.toString()}`);
};

export const getMarket = () => request<Market>("/market");

export const refreshPrices = () =>
  request<PriceRefresh>("/prices/refresh", { method: "POST" });

export const refreshFx = () => request<FxRefresh>("/fx/refresh", { method: "POST" });

export const refreshAll = () =>
  request<RefreshAll>("/refresh", { method: "POST" });
