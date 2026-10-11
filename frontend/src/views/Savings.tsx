/**
 * Savings: term deposits, and the two things that only happen at maturity.
 *
 * This page exists because a term deposit is not cash and is not a market
 * position, and treating it as either loses the one thing that makes it worth
 * tracking: the interest, which accrues by the day and which nobody wants to
 * recompute by hand.
 *
 * Three ideas shape the layout.
 *
 * 1. **Two figures, not one.** "Value today" is what it is worth right now;
 *    "value at maturity" is what the contract pays. Showing only the first
 *    hides the reason for holding it, and showing only the second would claim
 *    money that has not been earned yet.
 * 2. **A matured deposit is a decision, not a row.** Interest stops at
 *    maturity, so the record is marked and the two actions that make sense are
 *    put on it — roll it over, or take it out. The withdrawal creates the cash
 *    row itself, because doing that by hand is how the same million ends up
 *    counted twice.
 * 3. **A demand deposit is not a broken term deposit.** No maturity date means
 *    the money keeps earning with no end in sight, and the page says that
 *    rather than drawing an empty projection.
 */

import { useState } from "react";
import {
  createDeposit,
  deleteDeposit,
  depositSchedule,
  rollDeposit,
  updateDeposit,
  withdrawDeposit,
} from "../api/client";
import type {
  CashMoveOut,
  Currency,
  Deposit,
  DepositInput,
  Lang,
} from "../api/types";
import { CashMoveFields, CashMoveNotice } from "../components/CashMove";
import {
  CURRENCIES,
  DASH,
  formatDate,
  formatMoney,
  formatPercent,
  formatQuantity,
  useI18n,
} from "../i18n";
import { useApp } from "../state/AppContext";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Input,
  Modal,
  Notice,
  NumberInput,
  Select,
  SlideOver,
  Spinner,
  Stat,
  Textarea,
} from "../components/ui";

/**
 * Reads an amount typed in the reader's own number format.
 *
 * "1.234,56" for a Vietnamese reader, "1,234.56" for an English one. A lone
 * separator followed by exactly three digits is grouping; anything else is a
 * decimal mark, so a Vietnamese reader typing "2500.50" gets 2500.5 and not
 * 250050.
 */
function parseAmount(text: string, lang: Lang): number | null {
  const cleaned = text.replace(/[\s\u00a0]/g, "").replace(/[^\d.,-]/g, "");
  if (!cleaned) return null;
  const grouping = lang === "vi" ? /\.(?=\d{3}(\D|$))/g : /,(?=\d{3}(\D|$))/g;
  const decimal = lang === "vi" ? "," : ".";
  const value = Number(cleaned.replace(grouping, "").replace(decimal, "."));
  return Number.isFinite(value) ? value : null;
}

function messageOf(cause: unknown): string {
  if (cause instanceof Error) return cause.message;
  return String(cause);
}

function todayIso(): string {
  const now = new Date();
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** A date `days` after `iso`, for a default maturity. */
function addDays(iso: string, days: number): string {
  const date = new Date(`${iso}T00:00:00`);
  date.setDate(date.getDate() + days);
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function CurrencySelect({
  value,
  onChange,
}: {
  value: Currency;
  onChange: (code: Currency) => void;
}) {
  const { t } = useI18n();
  return (
    <Select
      label={t("field.currency")}
      hint={t("form.currency_hint")}
      value={value}
      onChange={(event) => {
        const next = CURRENCIES.find((code) => code === event.target.value);
        if (next) onChange(next);
      }}
    >
      {CURRENCIES.map((code) => (
        <option key={code} value={code}>
          {t(`currency.${code}` as const)}
        </option>
      ))}
    </Select>
  );
}

/**
 * One form for adding and for editing.
 *
 * Mounted only while it is open, so the initial state below is also the reset:
 * there is no stale form to clear when the next deposit is opened.
 */
function DepositForm({
  deposit,
  onClose,
  onSaved,
}: {
  deposit: Deposit | null;
  onClose: () => void;
  /** The row as the server stored it, so the page can report the cash side. */
  onSaved: (saved: Deposit) => void;
}) {
  const { t, lang } = useI18n();
  const app = useApp();
  const today = todayIso();

  const [name, setName] = useState(deposit?.name ?? "");
  const [currency, setCurrency] = useState<Currency>(
    deposit?.currency ?? app.baseCurrency,
  );
  const [principal, setPrincipal] = useState(
    deposit ? String(deposit.principal) : "",
  );
  const [rate, setRate] = useState(deposit ? String(deposit.annual_rate) : "");
  const [start, setStart] = useState(deposit?.start_date ?? today);
  const [maturity, setMaturity] = useState(deposit?.maturity_date ?? addDays(today, 181));
  const [demand, setDemand] = useState(deposit !== null && deposit.maturity_date === null);
  const [note, setNote] = useState(deposit?.note ?? "");

  const [attempted, setAttempted] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cashAmount, setCashAmount] = useState("");

  const amount = parseAmount(principal, lang);
  const rateValue = parseAmount(rate, lang);
  const rateInvalid = rateValue === null || rateValue < 0 || rateValue > 100;
  const datesInvalid = !demand && maturity < start;

  const submit = async () => {
    setAttempted(true);
    if (!name.trim() || amount === null || amount <= 0 || rateInvalid || datesInvalid) {
      return;
    }
    setSaving(true);
    setError(null);

    const body: DepositInput = {
      name: name.trim(),
      currency,
      principal: amount,
      annual_rate: rateValue,
      start_date: start,
      maturity_date: demand ? null : maturity,
      interest_mode: "at_maturity",
      note: note.trim() || null,
      // On an edit the server moves the difference in principal itself: a
      // second amount here would be a number the app kept two opinions about.
      cash_amount: deposit === null ? parseAmount(cashAmount, lang) : null,
    };

    try {
      if (deposit) {
        onSaved(await updateDeposit(deposit.id, body));
      } else {
        onSaved(await createDeposit(body));
      }
      // The overview total contains these deposits, so it is re-read rather
      // than left to disagree with this page.
      await app.refresh();
      onClose();
    } catch (cause) {
      setError(messageOf(cause));
    } finally {
      setSaving(false);
    }
  };

  return (
    <SlideOver
      open
      title={deposit ? t("dep.edit_title") : t("dep.add")}
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>{t("action.cancel")}</Button>
          <Button variant="primary" loading={saving} onClick={() => void submit()}>
            {t("action.save")}
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        {error && <Notice tone="error">{error}</Notice>}

        <Input
          autoFocus
          label={t("dep.bank")}
          value={name}
          onChange={(event) => setName(event.target.value)}
          error={attempted && !name.trim() ? t("form.required") : undefined}
        />

        <CurrencySelect value={currency} onChange={setCurrency} />

        <NumberInput
          label={t("dep.principal")}
          placeholder={formatQuantity(0, lang)}
          value={principal}
          onValueChange={setPrincipal}
          error={
            attempted && (amount === null || amount <= 0)
              ? t("form.required")
              : undefined
          }
        />

        <NumberInput
          label={t("dep.rate")}
          hint={t("dep.rate_hint")}
          value={rate}
          onValueChange={setRate}
          error={attempted && rateInvalid ? t("dep.rate_invalid") : undefined}
        />

        <Input
          type="date"
          label={t("dep.start_date")}
          value={start}
          onChange={(event) => setStart(event.target.value)}
        />

        <label className="flex items-start gap-2 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700">
          <input
            type="checkbox"
            className="mt-0.5"
            checked={demand}
            onChange={(event) => setDemand(event.target.checked)}
          />
          <span>
            <span className="block font-medium">{t("dep.demand")}</span>
            <span className="block text-xs text-slate-500">
              {t("dep.demand_hint")}
            </span>
          </span>
        </label>

        {!demand && (
          <Input
            type="date"
            label={t("dep.maturity_date")}
            hint={t("dep.maturity_hint")}
            value={maturity}
            min={start}
            onChange={(event) => setMaturity(event.target.value)}
            error={attempted && datesInvalid ? t("dep.dates_invalid") : undefined}
          />
        )}

        {/* The principal is money that leaves an account, so it is the amount
            the cash link moves. A deposit in dollars from a dong account is
            converted, and the figure is editable. */}
        {deposit === null ? (
          <CashMoveFields
            direction="out"
            amount={amount}
            currency={currency}
            cashAmount={cashAmount}
            onCashAmount={setCashAmount}
          />
        ) : (
          <p className="text-xs leading-relaxed text-slate-500">
            {t("move.edit_note")}
          </p>
        )}

        <Textarea
          label={`${t("form.note")} (${t("state.optional")})`}
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />
      </div>
    </SlideOver>
  );
}

/** The roll-over form: a new principal, rate and maturity, all pre-filled. */
function RollForm({
  deposit,
  onClose,
  onDone,
}: {
  deposit: Deposit;
  onClose: () => void;
  onDone: () => void;
}) {
  const { t, lang } = useI18n();
  const app = useApp();

  // The interest becomes the principal, which is what the bank does and what
  // the user would otherwise have to work out themselves.
  const [principal, setPrincipal] = useState(String(Math.round(deposit.value)));
  const [rate, setRate] = useState(String(deposit.annual_rate));
  const defaultMaturity =
    deposit.maturity_date === null
      ? addDays(todayIso(), 181)
      : addDays(
          deposit.maturity_date,
          Math.max(
            Math.round(
              (new Date(`${deposit.maturity_date}T00:00:00`).getTime() -
                new Date(`${deposit.start_date}T00:00:00`).getTime()) /
                86_400_000,
            ),
            1,
          ),
        );
  const [maturity, setMaturity] = useState(defaultMaturity);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const amount = parseAmount(principal, lang);
  const rateValue = parseAmount(rate, lang);

  const submit = async () => {
    if (amount === null || amount <= 0 || rateValue === null) return;
    setSaving(true);
    setError(null);
    try {
      await rollDeposit(deposit.id, {
        principal: amount,
        annual_rate: rateValue,
        start_date: deposit.maturity_date ?? todayIso(),
        maturity_date: maturity,
      });
      await app.refresh();
      onDone();
    } catch (cause) {
      setError(messageOf(cause));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open
      title={t("dep.roll_title")}
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>{t("action.cancel")}</Button>
          <Button variant="primary" loading={saving} onClick={() => void submit()}>
            {t("action.save")}
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        {error && <Notice tone="error">{error}</Notice>}
        <p className="text-xs leading-relaxed text-slate-500">
          {t("dep.roll_hint")}
        </p>
        <NumberInput
          label={t("dep.roll_new_principal")}
          value={principal}
          onValueChange={setPrincipal}
        />
        <NumberInput
          label={t("dep.roll_new_rate")}
          value={rate}
          onValueChange={setRate}
        />
        <Input
          type="date"
          label={t("dep.roll_new_maturity")}
          value={maturity}
          onChange={(event) => setMaturity(event.target.value)}
        />
      </div>
    </Modal>
  );
}

/** The withdrawal form: the amount, and the cash account it lands in. */
function WithdrawForm({
  deposit,
  onClose,
  onDone,
}: {
  deposit: Deposit;
  onClose: () => void;
  onDone: (closing: number, amount: number, cash: CashMoveOut | null) => void;
}) {
  const { t, lang } = useI18n();
  const app = useApp();

  const [amount, setAmount] = useState(String(Math.round(deposit.value)));
  const [cashAmount, setCashAmount] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const parsed = parseAmount(amount, lang);

  const submit = async () => {
    if (parsed === null || parsed < 0) return;
    setSaving(true);
    setError(null);
    try {
      const closed = await withdrawDeposit(deposit.id, {
        balance: parsed,
        cash_amount: parsed,
      });
      await app.refresh();
      onDone(deposit.id, parsed, closed.cash);
    } catch (cause) {
      setError(messageOf(cause));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open
      title={t("dep.withdraw_title")}
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>{t("action.cancel")}</Button>
          <Button variant="primary" loading={saving} onClick={() => void submit()}>
            {t("action.confirm")}
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        {error && <Notice tone="error">{error}</Notice>}
        <p className="text-xs leading-relaxed text-slate-500">
          {t("dep.withdraw_hint")}
        </p>
        <NumberInput
          label={t("dep.withdraw_amount")}
          value={amount}
          onValueChange={setAmount}
        />
        {/* Where it lands is not a decision: the pot of the deposit's own
            currency, which is the only cash there is. */}
        <CashMoveFields
          direction="in"
          amount={parsed}
          currency={deposit.currency}
          cashAmount={cashAmount}
          onCashAmount={setCashAmount}
        />
      </div>
    </Modal>
  );
}

/** The growth of one deposit from today to maturity, as plain bars. */
function Projection({ deposit }: { deposit: Deposit }) {
  const { t, lang } = useI18n();
  const [points, setPoints] = useState<Deposit[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (deposit.maturity_date === null) {
    return (
      <p className="text-xs text-slate-500">{t("dep.projection_empty")}</p>
    );
  }

  if (points === null && error === null) {
    // Fetched once, on first render of this row's projection.
    void depositSchedule(deposit.id)
      .then(setPoints)
      .catch((cause: unknown) => setError(messageOf(cause)));
  }

  if (error !== null) {
    return <p className="text-xs text-rose-600">{error}</p>;
  }
  if (points === null) {
    return <Spinner label={t("state.loading")} />;
  }
  if (points.length === 0) {
    return <p className="text-xs text-slate-500">{t("dep.projection_empty")}</p>;
  }

  const first = points[0];
  const last = points[points.length - 1];
  const gained = last.value - first.value;
  const share = last.value > 0 ? (gained / last.value) * 100 : 0;

  return (
    <div className="min-w-0 space-y-2">
      <div className="flex h-3 w-full overflow-hidden rounded-full bg-slate-100">
        <div
          className="h-full bg-slate-800"
          style={{ width: `${Math.max(100 - share, 0)}%` }}
        />
        <div
          className="h-full bg-emerald-500"
          style={{ width: `${share}%` }}
        />
      </div>
      <div className="flex min-w-0 flex-wrap justify-between gap-x-4 gap-y-1 text-xs text-slate-500">
        <span>
          {t("dep.value")}:{" "}
          <span className="tabular-nums text-slate-900">
            {formatMoney(first.value, deposit.currency, lang)}
          </span>
        </span>
        <span>
          {t("dep.value_at_maturity")}:{" "}
          <span className="tabular-nums font-medium text-slate-900">
            {formatMoney(last.value_at_maturity, deposit.currency, lang)}
          </span>
        </span>
        <span className="text-emerald-600">
          +{formatMoney(gained, deposit.currency, lang)}
        </span>
      </div>
    </div>
  );
}

export function Savings() {
  const { t, lang } = useI18n();
  const app = useApp();

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Deposit | null>(null);
  const [rolling, setRolling] = useState<Deposit | null>(null);
  const [withdrawing, setWithdrawing] = useState<Deposit | null>(null);
  const [removing, setRemoving] = useState<Deposit | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  /** What the last trade did to a cash balance, or why it did nothing. */
  const [cashNotice, setCashNotice] = useState<CashMoveOut | null>(null);

  const portfolio = app.portfolio;
  if (!portfolio) return <Spinner label={t("state.loading")} />;

  const base = app.baseCurrency;
  const rows = portfolio.deposits;

  const subtotals = CURRENCIES.map((code) => {
    const held = rows.filter((row) => row.currency === code);
    return {
      code,
      count: held.length,
      amount: held.reduce((sum, row) => sum + row.value, 0),
    };
  }).filter((entry) => entry.count > 0);

  const totalInterest = rows.reduce((sum, row) => sum + (row.interest_base ?? 0), 0);

  const confirmDelete = async () => {
    if (removing === null) return;
    setBusy(true);
    try {
      const removed = await deleteDeposit(removing.id);
      await app.refresh();
      setCashNotice(removed.cash);
      setRemoving(null);
      setError(null);
    } catch (cause) {
      setError(messageOf(cause));
    } finally {
      setBusy(false);
    }
  };

  /** How far through its term a deposit is, as a percentage. */
  const progress = (row: Deposit): number | null => {
    if (row.maturity_date === null) return null;
    const start = new Date(`${row.start_date}T00:00:00`).getTime();
    const end = new Date(`${row.maturity_date}T00:00:00`).getTime();
    const now = new Date(`${row.as_of}T00:00:00`).getTime();
    if (end <= start) return 100;
    return Math.min(Math.max(((now - start) / (end - start)) * 100, 0), 100);
  };

  return (
    <div className="space-y-4">
      <CashMoveNotice cash={cashNotice} />

      {error && (
        <Notice
          tone="error"
          title={t("form.save_failed")}
          onDismiss={() => setError(null)}
        >
          {error}
        </Notice>
      )}

      {status && <Notice tone="info">{status}</Notice>}

      <Card
        title={t("dep.title")}
        subtitle={t("dep.note")}
        actions={
          <Button
            variant="primary"
            onClick={() => {
              setEditing(null);
              setFormOpen(true);
            }}
          >
            {t("dep.add")}
          </Button>
        }
      >
        {rows.length === 0 ? (
          <EmptyState
            title={t("dep.none_title")}
            body={t("dep.none_body")}
            action={
              <Button
                variant="primary"
                onClick={() => {
                  setEditing(null);
                  setFormOpen(true);
                }}
              >
                {t("dep.add")}
              </Button>
            }
          />
        ) : (
          <div className="space-y-3">
            {rows.map((row) => {
              const share = progress(row);
              const counted = row.value_base !== null;
              return (
                <div
                  key={row.id}
                  className={`rounded-xl border px-4 py-3 ${
                    row.matured
                      ? "border-amber-200 bg-amber-50/50"
                      : "border-slate-200 bg-white"
                  }`}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium text-slate-900">
                          {row.name}
                        </span>
                        <Badge tone="info">
                          {t(`currency.${row.currency}` as const)}
                        </Badge>
                        {row.matured ? (
                          <Badge tone="warning">{t("dep.matured")}</Badge>
                        ) : row.maturity_date === null ? (
                          <Badge>{t("dep.demand")}</Badge>
                        ) : (
                          <Badge tone="positive">{t("dep.accruing")}</Badge>
                        )}
                        {!counted && (
                          <Badge tone="warning">
                            {t("reason.not_convertible")}
                          </Badge>
                        )}
                      </div>
                      <p className="mt-1 text-xs text-slate-500">
                        {formatMoney(row.principal, row.currency, lang)} ·{" "}
                        {formatQuantity(row.annual_rate, lang, 4)}
                        {t("dep.rate_unit")} · {formatDate(row.start_date, lang)}
                        {row.maturity_date
                          ? ` → ${formatDate(row.maturity_date, lang)}`
                          : ""}
                      </p>
                    </div>

                    <div className="flex shrink-0 flex-wrap items-center gap-1">
                      {row.matured && (
                        <>
                          <Button size="sm" variant="primary" onClick={() => setRolling(row)}>
                            {t("dep.roll")}
                          </Button>
                          <Button size="sm" onClick={() => setWithdrawing(row)}>
                            {t("dep.withdraw")}
                          </Button>
                        </>
                      )}
                      <Button
                        size="sm"
                        onClick={() => {
                          setEditing(row);
                          setFormOpen(true);
                        }}
                      >
                        {t("action.edit")}
                      </Button>
                      <Button size="sm" onClick={() => setRemoving(row)}>
                        {t("action.delete")}
                      </Button>
                    </div>
                  </div>

                  {/* The term so far, as a bar. A demand deposit has no end to
                      measure against, so it gets none rather than a full bar
                      that would mean "finished". */}
                  {share !== null && (
                    <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-100">
                      <div
                        className={`h-full ${row.matured ? "bg-amber-500" : "bg-slate-800"}`}
                        style={{ width: `${share}%` }}
                      />
                    </div>
                  )}

                  <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                    <Stat
                      label={t("dep.value")}
                      value={formatMoney(row.value, row.currency, lang)}
                    />
                    <Stat
                      label={t("dep.interest_accrued")}
                      value={formatMoney(row.interest_accrued, row.currency, lang)}
                      tone={row.interest_accrued > 0 ? "positive" : "neutral"}
                      hint={
                        counted
                          ? formatMoney(row.interest_base, base, lang)
                          : undefined
                      }
                    />
                    <Stat
                      label={
                        row.matured
                          ? t("dep.value_at_maturity")
                          : t("dep.interest_at_maturity")
                      }
                      value={
                        row.matured
                          ? formatMoney(row.value_at_maturity, row.currency, lang)
                          : formatMoney(
                              row.value_at_maturity - row.principal,
                              row.currency,
                              lang,
                            )
                      }
                    />
                    <Stat
                      label={t("dep.value_in_base")}
                      value={
                        counted
                          ? formatMoney(row.value_base, base, lang)
                          : DASH
                      }
                      hint={
                        row.days_remaining === null
                          ? t("dep.term_days", { days: row.days_accrued })
                          : `${t("dep.days_accrued")}: ${row.days_accrued} · ${t(
                              "dep.days_remaining",
                            )}: ${row.days_remaining}`
                      }
                    />
                  </div>

                  {row.matured && (
                    <p className="mt-3 text-xs leading-relaxed text-amber-800">
                      {t("dep.matured_hint")}
                    </p>
                  )}

                  <div className="mt-3 min-w-0 border-t border-slate-100 pt-3">
                    <p className="mb-2 text-xs font-medium text-slate-600">
                      {t("dep.projection")}
                    </p>
                    <Projection deposit={row} />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {rows.length > 0 && (
        <Card title={t("dep.subtotal")}>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {subtotals.map((entry) => (
              <Stat
                key={entry.code}
                label={t(`currency.${entry.code}` as const)}
                value={formatMoney(entry.amount, entry.code, lang)}
              />
            ))}
            <Stat
              label={t("dep.value_in_base")}
              value={formatMoney(portfolio.deposit_value, base, lang)}
            />
            <Stat
              label={t("dep.interest_accrued")}
              value={formatMoney(totalInterest, base, lang)}
              tone={totalInterest > 0 ? "positive" : "neutral"}
              hint={
                portfolio.deposit_value > 0
                  ? formatPercent(
                      (totalInterest / portfolio.deposit_value) * 100,
                      lang,
                    )
                  : undefined
              }
            />
          </div>
        </Card>
      )}

      {formOpen && (
        <DepositForm
          deposit={editing}
          onSaved={(saved) => setCashNotice(saved.cash)}
          onClose={() => {
            setFormOpen(false);
            setEditing(null);
          }}
        />
      )}

      {rolling && (
        <RollForm
          deposit={rolling}
          onClose={() => setRolling(null)}
          onDone={() => {
            setRolling(null);
            setStatus(t("dep.roll_done"));
          }}
        />
      )}

      {withdrawing && (
        <WithdrawForm
          deposit={withdrawing}
          onClose={() => setWithdrawing(null)}
          onDone={(_id, amount, cash) => {
            setWithdrawing(null);
            setCashNotice(cash);
            setStatus(t("dep.withdraw_done", { amount }));
          }}
        />
      )}

      <Modal
        open={removing !== null}
        title={t("action.delete")}
        onClose={() => setRemoving(null)}
        footer={
          <>
            <Button onClick={() => setRemoving(null)}>{t("action.cancel")}</Button>
            <Button variant="danger" loading={busy} onClick={() => void confirmDelete()}>
              {t("action.delete")}
            </Button>
          </>
        }
      >
        <p>{t("dep.delete_confirm", { name: removing?.name ?? "" })}</p>
      </Modal>
    </div>
  );
}

export default Savings;
