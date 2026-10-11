/**
 * Market: what is cached, dated, and honest about being old.
 *
 * Two tables and two buttons, because the two feeds fail independently. A
 * quote and a rate are facts with a date attached, never live values, so the
 * page shows both dates: the session a price belongs to and the moment the
 * source was last asked. A stale number with a visible date is usable; a stale
 * number without one is a lie, and the difference is this page's whole job.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError, getMarket, refreshFx, refreshPrices } from "../api/client";
import type {
  FxRefresh,
  FxRow,
  Market as MarketData,
  PriceRefresh,
} from "../api/types";
import {
  formatDate,
  formatDateTime,
  formatMoney,
  formatQuantity,
  useI18n,
} from "../i18n";
import { useApp } from "../state/AppContext";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Notice,
  Spinner,
  Table,
  Td,
  Th,
} from "../components/ui";

function messageOf(cause: unknown): string {
  if (cause instanceof ApiError) return cause.message;
  if (cause instanceof Error) return cause.message;
  return String(cause);
}

function todayIso(): string {
  const now = new Date();
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/**
 * Staleness is derived the same way the server derives it: a rate that is the
 * built-in placeholder, or one that does not belong to today, is flagged. The
 * definitional 1:1 row of the base currency is neither.
 */
function rateIsStale(row: FxRow, today: string): boolean {
  return row.source === "seed" || row.as_of < today;
}

export function Market() {
  const { t, lang } = useI18n();
  const app = useApp();

  const [data, setData] = useState<MarketData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"prices" | "rates" | null>(null);
  const [priceReport, setPriceReport] = useState<PriceRefresh | null>(null);
  const [fxReport, setFxReport] = useState<FxRefresh | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await getMarket());
      setError(null);
    } catch (cause) {
      setError(messageOf(cause));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const onPrices = async () => {
    setBusy("prices");
    setPriceReport(null);
    try {
      const report = await refreshPrices();
      setPriceReport(report);
      await load();
      // Every figure on every other page was computed from this cache.
      await app.refresh();
    } catch (cause) {
      setError(messageOf(cause));
    } finally {
      setBusy(null);
    }
  };

  const onRates = async () => {
    setBusy("rates");
    setFxReport(null);
    try {
      const report = await refreshFx();
      setFxReport(report);
      await load();
      await app.refresh();
    } catch (cause) {
      setError(messageOf(cause));
    } finally {
      setBusy(null);
    }
  };

  if (loading && data === null) return <Spinner label={t("state.loading")} />;

  const prices = data?.prices ?? [];
  const rates = data?.rates ?? [];
  const today = todayIso();
  const seedInUse = rates.some((row) => row.source === "seed");

  return (
    <div className="space-y-4">
      {error && (
        <Notice tone="error" title={t("state.error")} onDismiss={() => setError(null)}>
          {error}
        </Notice>
      )}

      <Card
        title={t("market.prices")}
        subtitle={t("market.prices_note")}
        actions={
          <Button
            variant="primary"
            loading={busy === "prices"}
            disabled={busy !== null}
            onClick={() => void onPrices()}
          >
            {t("market.refresh_prices")}
          </Button>
        }
      >
        {priceReport && (
          <div className="mb-3 space-y-2">
            {priceReport.failed.length > 0 && (
              <Notice
                tone="error"
                title={t("market.refresh_failed", {
                  list: priceReport.failed.map((failure) => failure.symbol).join(", "),
                })}
              >
                <ul className="space-y-1">
                  {priceReport.failed.map((failure) => (
                    <li key={failure.symbol}>
                      {failure.symbol}: {failure.error}
                    </li>
                  ))}
                </ul>
              </Notice>
            )}
            {priceReport.refreshed.length > 0 && (
              <Badge tone="positive">
                {t("market.refresh_done", { count: priceReport.refreshed.length })}
              </Badge>
            )}
          </div>
        )}

        {prices.length === 0 ? (
          <EmptyState title={t("market.nothing_cached")} />
        ) : (
          <Table
            head={
              <>
                <Th>{t("market.symbol")}</Th>
                <Th align="right">{t("market.price")}</Th>
                <Th>{t("market.currency_of_quote")}</Th>
                <Th>{t("market.close_date")}</Th>
                <Th>{t("market.fetched_at")}</Th>
                <Th>{t("market.row_error")}</Th>
              </>
            }
          >
            {prices.map((row) => (
              <tr key={row.symbol}>
                <Td className="font-medium text-slate-900">{row.symbol}</Td>
                <Td align="right">
                  {row.currency
                    ? formatMoney(row.price, row.currency, lang)
                    : formatQuantity(row.price, lang)}
                </Td>
                <Td>{row.currency ?? t("state.unknown")}</Td>
                <Td>{formatDate(row.as_of, lang)}</Td>
                <Td>{formatDateTime(row.fetched_at, lang)}</Td>
                <Td>
                  {row.error && (
                    <span title={row.error}>
                      <Badge tone="warning">{t("market.row_error")}</Badge>
                    </span>
                  )}
                </Td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      <Card
        title={t("market.rates")}
        subtitle={t("market.rates_note")}
        actions={
          <Button
            variant="primary"
            loading={busy === "rates"}
            disabled={busy !== null}
            onClick={() => void onRates()}
          >
            {t("market.refresh_rates")}
          </Button>
        }
      >
        <div className="mb-3 space-y-2">
          {seedInUse && <Notice tone="warning">{t("market.seed_warning")}</Notice>}

          {fxReport && (
            <>
              {fxReport.error && (
                <Notice tone="error" title={t("market.refresh_error")}>
                  {fxReport.error}
                </Notice>
              )}
              {fxReport.stored.length > 0 && (
                <Badge tone="positive">
                  {t("market.refresh_done", { count: fxReport.stored.length })}
                </Badge>
              )}
            </>
          )}
        </div>

        {rates.length === 0 ? (
          <EmptyState title={t("market.no_rates")} />
        ) : (
          <Table
            head={
              <>
                <Th>{t("market.base")}</Th>
                <Th>{t("field.currency")}</Th>
                <Th align="right">{t("market.rate")}</Th>
                <Th>{t("market.rate_date")}</Th>
                <Th>{t("market.source")}</Th>
              </>
            }
          >
            {rates.map((row) => (
              <tr key={`${row.base}-${row.currency}-${row.as_of}`}>
                <Td>{row.base}</Td>
                <Td>{row.currency}</Td>
                <Td align="right">{formatQuantity(row.rate, lang)}</Td>
                <Td>{formatDate(row.as_of, lang)}</Td>
                <Td>
                  <span className="flex items-center gap-1">
                    <Badge tone={row.source === "seed" ? "warning" : "neutral"}>
                      {row.source === "seed"
                        ? t("market.source_seed")
                        : row.source === "feed"
                          ? t("market.source_feed")
                          : t("market.source_other")}
                    </Badge>
                    {rateIsStale(row, today) && (
                      <Badge tone="warning">{t("market.stale")}</Badge>
                    )}
                  </span>
                </Td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  );
}

export default Market;
