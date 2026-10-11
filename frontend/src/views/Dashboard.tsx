/**
 * The overview: one total, the parts it is made of, and everything left out.
 *
 * Three rules borrowed from the backend and made visible here, because a
 * dashboard is where a number is most likely to be believed:
 *
 * 1. **The total is a sum of conversions.** Cash and market positions are
 *    converted before they meet, so they are shown already in the base
 *    currency and never in the currency they happen to be quoted in.
 * 2. **What could not be converted is named, not dropped.** A total that is
 *    quietly short is worse than no total, so `unconverted` is printed beside
 *    it with the reason and the sentence that says the figure excludes it.
 * 3. **History keeps the currency it was written in.** Points written in two
 *    different bases are never drawn as a single line, because that line would
 *    be a currency movement wearing the costume of performance.
 */

import { useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { AssetKind, RefreshFailure, UnpricedReason } from "../api/types";
import {
  AllocationPie,
  Badge,
  Button,
  Card,
  EmptyState,
  Notice,
  Spinner,
  Stat,
  Table,
  Td,
  Th,
} from "../components/ui";
import {
  DASH,
  formatDate,
  formatMoney,
  formatMonthDay,
  formatPercent,
  formatSignedMoney,
  useLang,
  useT,
} from "../i18n";
import { useApp } from "../state/AppContext";

/**
 * Every kind, in the order they are always listed.
 *
 * This list — not the response — decides what the allocation shows. The API
 * does keep empty kinds, but a kind worth nothing must survive a change on the
 * other side of the wire too: a pie that silently loses its "crypto" slice
 * reads as a bug, while a legend that says 0 is information.
 */
const KIND_ORDER: AssetKind[] = ["stock", "fund", "crypto", "cash"];

export function Dashboard() {
  const t = useT();
  const lang = useLang();
  const app = useApp();

  const [refreshing, setRefreshing] = useState(false);
  const [refreshed, setRefreshed] = useState<number | null>(null);
  const [failures, setFailures] = useState<RefreshFailure[]>([]);
  const [recording, setRecording] = useState(false);
  const [recorded, setRecorded] = useState(false);

  const portfolio = app.portfolio;
  const base = app.baseCurrency;
  const points = app.history?.points ?? [];

  // Which currencies the history was written in, in the order they appear.
  const writtenIn: string[] = [];
  for (const point of points) {
    if (!writtenIn.includes(point.base_currency)) {
      writtenIn.push(point.base_currency);
    }
  }
  const mixedBase = writtenIn.length > 1;
  const chartBase = mixedBase ? base : (writtenIn[0] ?? base);
  // A mixed series is not plotted whole: only the points in one currency are,
  // so the line has a single unit from end to end. The warning below says so.
  const chartPoints = mixedBase
    ? points.filter((point) => point.base_currency === base)
    : points;

  const reasonText = (reason: UnpricedReason | null) =>
    reason === null ? t("state.unknown") : t(`reason.${reason}` as const);

  if (portfolio === null) {
    return (
      <Card>
        <Spinner label={t("state.loading")} />
      </Card>
    );
  }

  const staleRates = portfolio.rates.filter((rate) => rate.stale);
  const gainUnknown = portfolio.gain === null;
  const gainTone =
    portfolio.gain === null || portfolio.gain === 0
      ? "neutral"
      : portfolio.gain > 0
        ? "positive"
        : "negative";

  const byKind = KIND_ORDER.map((kind) => ({
    kind,
    value: portfolio.by_kind.find((row) => row.kind === kind)?.value ?? 0,
  }));

  const chartData = chartPoints.map((point) => ({
    label: formatMonthDay(point.as_of, lang),
    value: point.total,
  }));

  const onRefresh = async () => {
    setRefreshing(true);
    setRefreshed(null);
    setFailures([]);
    try {
      // `refreshAll()` fetches the new prices and rates and then reloads
      // everything — which is `refresh()`. Calling both would ask the server
      // for the same three responses twice.
      const report = await app.refreshAll();
      setFailures(report.prices.failed);
      setRefreshed(report.prices.refreshed.length);
    } catch {
      // The provider has already put the message in `app.error`, which the
      // shell prints above the page; a second copy here would duplicate it.
    } finally {
      setRefreshing(false);
    }
  };

  const onRecord = async () => {
    setRecording(true);
    setRecorded(false);
    try {
      await app.snapshot();
      setRecorded(true);
    } catch {
      // As above: the shell owns the error banner.
    } finally {
      setRecording(false);
    }
  };

  const refreshButton = (
    <Button
      size="sm"
      variant="primary"
      loading={refreshing}
      onClick={() => {
        void onRefresh();
      }}
    >
      {t("dash.refresh")}
    </Button>
  );

  const notices = (
    <>
      {staleRates.length > 0 && (
        <Notice tone="warning" title={t("dash.rates")}>
          <ul className="space-y-1">
            {staleRates.map((rate) => (
              <li
                key={rate.currency}
                className="flex flex-wrap items-baseline gap-x-2"
              >
                <span className="font-medium">{rate.currency}</span>
                <span>{t("dash.rate_stale")}</span>
                <span>
                  {t("dash.rate_as_of", { date: formatDate(rate.as_of, lang) })}
                </span>
              </li>
            ))}
          </ul>
        </Notice>
      )}

      {portfolio.unconverted.length > 0 && (
        <Notice tone="warning" title={t("dash.unconverted")}>
          <p>{t("dash.unconverted_hint")}</p>
          <p className="mt-1">{t("reason.hint")}</p>
          <ul className="mt-2 space-y-1">
            {portfolio.unconverted.map((item) => (
              <li
                key={`${item.kind}-${item.id}`}
                className="flex flex-wrap items-center gap-2"
              >
                <span className="font-medium">{item.label}</span>
                <Badge tone="warning">{reasonText(item.reason)}</Badge>
                <span>{t("state.not_counted")}</span>
              </li>
            ))}
          </ul>
        </Notice>
      )}

      {failures.length > 0 && (
        <Notice
          tone="error"
          title={t("dash.refresh_failed", {
            list: failures.map((failure) => failure.symbol).join(", "),
          })}
        >
          <ul className="space-y-1">
            {failures.map((failure) => (
              <li
                key={failure.symbol}
                className="flex flex-wrap items-baseline gap-x-2"
              >
                <span className="font-medium">{failure.symbol}</span>
                <span>{failure.error}</span>
              </li>
            ))}
          </ul>
        </Notice>
      )}

      {refreshed !== null && failures.length === 0 && (
        <Notice tone="info">{t("dash.refresh_done", { count: refreshed })}</Notice>
      )}

      {recorded && <Notice tone="info">{t("dash.snapshot_done")}</Notice>}
    </>
  );

  // Nothing at all: a total of zero would be a claim about a portfolio that
  // does not exist yet, so the page explains how to start one instead.
  if (portfolio.counts.assets === 0 && portfolio.counts.cash === 0) {
    return (
      <div className="space-y-4">
        {notices}
        <Card title={t("dash.title")} actions={refreshButton}>
          <EmptyState title={t("dash.empty_title")} body={t("dash.empty_body")} />
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {notices}

      <Card title={t("dash.title")} actions={refreshButton}>
        <Stat
          label={t("dash.total")}
          value={formatMoney(portfolio.total, base, lang)}
        />

        <div className="mt-4 grid gap-4 border-t border-slate-100 pt-4 sm:grid-cols-2 lg:grid-cols-4">
          <Stat
            label={t("dash.market_value")}
            value={formatMoney(portfolio.market_value, base, lang)}
          />
          <Stat
            label={t("dash.cash_value")}
            value={formatMoney(portfolio.cash_value, base, lang)}
          />

          {gainUnknown ? (
            // No gain is printed at all when one is not known: the figure is
            // absent because a position has no cost recorded, and the reason it
            // is absent is more useful than a zero pretending to be a result.
            <div className="min-w-0">
              <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
                {t("dash.gain")}
              </div>
              <p className="mt-1 text-xs leading-relaxed text-slate-500">
                {t("dash.gain_unknown")}
              </p>
            </div>
          ) : (
            <>
              <Stat
                label={t("dash.gain")}
                value={formatSignedMoney(portfolio.gain, base, lang)}
                tone={gainTone}
              />
              <Stat
                label={t("dash.gain_pct")}
                value={formatPercent(portfolio.gain_pct, lang)}
                tone={gainTone}
              />
            </>
          )}
        </div>

        <p className="mt-4 flex flex-wrap gap-x-4 text-xs text-slate-500">
          <span>
            {t("dash.count_assets", { count: portfolio.counts.assets })}
          </span>
          <span>{t("dash.count_cash", { count: portfolio.counts.cash })}</span>
        </p>
      </Card>

      <Card title={t("dash.allocation")} subtitle={t("dash.allocation_hint")}>
        <div className="grid items-center gap-6 sm:grid-cols-2">
          <AllocationPie
            slices={byKind.map((row) => ({
              label: t(`kind.${row.kind}` as const),
              value: row.value,
            }))}
          />
          <ul className="space-y-3">
            {byKind.map((row) => (
              <li
                key={row.kind}
                className="flex items-center justify-between gap-3"
              >
                <Badge tone={row.value > 0 ? "info" : "neutral"}>
                  {t(`kind.${row.kind}` as const)}
                </Badge>
                <span className="text-sm tabular-nums text-slate-900">
                  {formatMoney(row.value, base, lang)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </Card>

      <Card title={t("dash.exposure")} subtitle={t("dash.exposure_hint")}>
        {portfolio.by_currency.length === 0 ? (
          <EmptyState title={t("state.empty")} />
        ) : (
          <Table
            head={
              <>
                <Th>{t("field.currency")}</Th>
                <Th align="right">{t("dash.exposure_amount")}</Th>
                <Th align="right">{t("dash.exposure_in_base")}</Th>
              </>
            }
          >
            {portfolio.by_currency.map((row) => (
              <tr key={row.currency}>
                <Td>
                  <Badge>{row.currency}</Badge>
                </Td>
                {/* The amount is shown in its own currency, beside — never
                    instead of — the same money in the base. The pair is the
                    point: two rows' amounts are not comparable. */}
                <Td align="right" className="tabular-nums">
                  {formatMoney(row.amount, row.currency, lang)}
                </Td>
                <Td align="right" className="tabular-nums font-medium text-slate-900">
                  {formatMoney(row.value_base, base, lang)}
                </Td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      <Card
        title={t("dash.history")}
        actions={
          <Button
            size="sm"
            loading={recording}
            onClick={() => {
              void onRecord();
            }}
          >
            {t("dash.snapshot")}
          </Button>
        }
      >
        {mixedBase && (
          <div className="mb-4">
            <Notice tone="warning">{t("dash.history_mixed_base")}</Notice>
          </div>
        )}

        {chartData.length === 0 ? (
          <EmptyState title={t("state.empty")} body={t("dash.history_empty")} />
        ) : (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={chartData}
                margin={{ top: 8, right: 8, bottom: 0, left: 8 }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="#e2e8f0"
                  vertical={false}
                />
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 11, fill: "#64748b" }}
                  tickLine={false}
                  axisLine={false}
                  minTickGap={24}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: "#64748b" }}
                  tickLine={false}
                  axisLine={false}
                  width={96}
                  tickFormatter={(value: number) =>
                    formatMoney(value, chartBase, lang)
                  }
                />
                {/* Recharts types the tooltip value as possibly absent, so it
                    is narrowed rather than asserted: an unknown point prints
                    the dash, exactly as every other unknown figure does. */}
                <Tooltip
                  formatter={(value) =>
                    typeof value === "number"
                      ? formatMoney(value, chartBase, lang)
                      : DASH
                  }
                />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke="#0f172a"
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>
    </div>
  );
}

export default Dashboard;
