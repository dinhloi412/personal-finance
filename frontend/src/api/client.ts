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
  CashAccount,
  CashInput,
  CashPatch,
  History,
  Market,
  Portfolio,
  PriceRefresh,
  FxRefresh,
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

export const deleteAsset = (id: number) =>
  request<void>(`/assets/${id}`, { method: "DELETE" });

export const priceAsset = (id: number) =>
  request<Asset>(`/assets/${id}/price`, { method: "POST" });

// ---------------------------------------------------------------------------
// Cash
// ---------------------------------------------------------------------------

export const listCash = () => request<CashAccount[]>("/cash");

export const createCash = (input: CashInput) =>
  request<CashAccount>("/cash", { method: "POST", json: input });

export const updateCash = (id: number, patch: CashPatch) =>
  request<CashAccount>(`/cash/${id}`, { method: "PATCH", json: patch });

export const deleteCash = (id: number) =>
  request<void>(`/cash/${id}`, { method: "DELETE" });

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
