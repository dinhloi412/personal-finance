/**
 * Cash: a balance you write down, edited where it is shown — and, when trades
 * are linked to it, the history of everything that moved it.
 *
 * The inline editor is the point of the page. "The money moved" is a thought
 * the user has while looking at a number they already know, so the balance cell
 * becomes an input in place — Enter saves, Escape walks away — and a form is
 * kept for the rarer jobs: creating an account, renaming it, changing currency.
 *
 * Subtotals stay in their own currency. Adding 5 000 000 ₫ to 200 $ is not a
 * number; only the converted total in the base currency is.
 */

import { useState } from "react";

import { cashEntry, updateCash } from "../api/client";
import type { CashAccount, CashEntry, CashMovement, Lang } from "../api/types";
import { moveName } from "../components/CashMove";
import {
  CURRENCIES,
  DASH,
  formatDate,
  formatMoney,
  formatQuantity,
  formatSignedMoney,
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
  Spinner,
  Stat,
  Table,
  Td,
  Textarea,
  Th,
} from "../components/ui";

/**
 * Reads an amount typed in the reader's own number format: "1.234,56" for a
 * Vietnamese reader, "1,234.56" for an English one. Returns null when the field
 * is not a number at all, so the caller refuses instead of writing a zero.
 */
function parseAmount(text: string, lang: Lang): number | null {
  const cleaned = text.replace(/[\s\u00a0]/g, "").replace(/[^\d.,-]/g, "");
  if (!cleaned) return null;
  // Only a separator followed by exactly three digits is grouping; "2500.50"
  // typed by a Vietnamese reader is a decimal point, not a thousands mark.
  const grouping = lang === "vi" ? /\.(?=\d{3}(\D|$))/g : /,(?=\d{3}(\D|$))/g;
  const decimal = lang === "vi" ? "," : ".";
  const value = Number(cleaned.replace(grouping, "").replace(decimal, "."));
  return Number.isFinite(value) ? value : null;
}

function messageOf(cause: unknown): string {
  if (cause instanceof Error) return cause.message;
  return String(cause);
}

/**
 * Money in or out of a balance, with a reason.
 *
 * The Cash page's own action, and the one that is not a trade: a salary, a
 * bill, a gift. Two facts and a note — where it went, how much, and why — and
 * no category, because a category is the first step to a budget.
 */
function EntryForm({
  account,
  onClose,
  onDone,
}: {
  account: CashAccount;
  onClose: () => void;
  onDone: (message: string) => void;
}) {
  const { t, lang } = useI18n();
  const app = useApp();

  const [direction, setDirection] = useState<CashEntry["direction"]>("in");
  const [amount, setAmount] = useState("");
  const [day, setDay] = useState(new Date().toISOString().slice(0, 10));
  const [reason, setReason] = useState("");
  const [attempted, setAttempted] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const parsed = parseAmount(amount, lang);
  const ok = parsed !== null && parsed > 0;

  const submit = async () => {
    setAttempted(true);
    if (!ok || parsed === null) return;
    setSaving(true);
    setError(null);
    try {
      const result = await cashEntry(account.id, {
        amount: parsed,
        direction,
        occurred_on: day || undefined,
        note: reason.trim() || null,
      });
      await app.refresh();
      onDone(
        t(
          direction === "in" ? "cash.entry_done_in" : "cash.entry_done_out",
          {
            amount: formatMoney(parsed, result.account.currency, lang),
            name: result.account.name,
          },
        ),
      );
    } catch (cause) {
      setError(messageOf(cause));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open
      title={t("cash.entry_title")}
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose} disabled={saving}>
            {t("action.cancel")}
          </Button>
          <Button
            variant="primary"
            loading={saving}
            disabled={!ok}
            onClick={() => void submit()}
          >
            {t("action.save")}
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <p className="text-xs leading-relaxed text-slate-500">
          {t("cash.entry_hint")}
        </p>
        {error && (
          <Notice tone="error" title={t("cash.entry_failed")}>
            {error}
          </Notice>
        )}

        <Select
          label={t("cash.entry_direction")}
          value={direction}
          onChange={(event) =>
            setDirection(event.target.value === "out" ? "out" : "in")
          }
        >
          <option value="in">{t("cash.entry_in")}</option>
          <option value="out">{t("cash.entry_out")}</option>
        </Select>

        <NumberInput
          label={`${t("cash.entry_amount")} (${account.currency})`}
          value={amount}
          onValueChange={setAmount}
          error={attempted && !ok ? t("form.required") : undefined}
        />

        <Input
          type="date"
          label={t("cash.entry_date")}
          value={day}
          onChange={(event) => setDay(event.target.value)}
        />

        <Input
          label={`${t("cash.entry_reason")} (${t("state.optional")})`}
          hint={t("cash.entry_reason_hint")}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        />
      </div>
    </Modal>
  );
}

/**
 * Every movement that has touched these accounts, newest first.
 *
 * Its own card rather than a column, because a balance and the list of things
 * that changed it are two different sizes of fact: the table above answers
 * "how much is there", and this answers "why". Filtered to one account at a
 * time by the button on the row it belongs to.
 */
function MovementsCard({
  accounts,
  movements,
  account,
  onAccount,
}: {
  accounts: CashAccount[];
  movements: CashMovement[];
  account: number | "all";
  onAccount: (value: number | "all") => void;
}) {
  const { t, lang } = useI18n();
  const nameOf = (id: number) =>
    accounts.find((row) => row.id === id)?.name ?? t("state.unknown");

  const shown =
    account === "all"
      ? movements
      : movements.filter((row) => row.account_id === account);

  return (
    <Card
      title={t("cash.move_log")}
      subtitle={t("cash.move_log_hint")}
      actions={
        accounts.length > 1 ? (
          <div className="w-48">
            <Select
              label={t("cash.move_account")}
              value={String(account)}
              onChange={(event) =>
                onAccount(
                  event.target.value === "all" ? "all" : Number(event.target.value),
                )
              }
            >
              <option value="all">{t("cash.move_all")}</option>
              {accounts.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.name}
                </option>
              ))}
            </Select>
          </div>
        ) : undefined
      }
    >
      {shown.length === 0 ? (
        <EmptyState title={t("cash.move_log_empty")} />
      ) : (
        <Table
          head={
            <>
              <Th>{t("cash.move_date")}</Th>
              {account === "all" && <Th>{t("cash.move_account")}</Th>}
              <Th>{t("cash.move_what")}</Th>
              <Th align="right">{t("cash.move_amount")}</Th>
            </>
          }
        >
          {shown.map((row) => (
            <tr key={row.id}>
              <Td className="whitespace-nowrap text-slate-500">
                {formatDate(row.occurred_on, lang)}
              </Td>
              {account === "all" && <Td>{nameOf(row.account_id)}</Td>}
              <Td>
                <div className="font-medium text-slate-900">
                  {row.subject === "cash" && row.action === "adjust"
                    ? t("cash.adjust_line")
                    : t(`move.action.${row.action}` as const, {
                        name: moveName(row),
                      })}
                </div>
                {row.note && (
                  <div className="text-xs text-slate-500">{row.note}</div>
                )}
              </Td>
              <Td align="right" className="tabular-nums">
                <span
                  className={
                    row.amount === 0
                      ? ""
                      : row.amount > 0
                        ? "text-emerald-600"
                        : "text-rose-600"
                  }
                >
                  {formatSignedMoney(row.amount, row.currency, lang)}
                </span>
              </Td>
            </tr>
          ))}
        </Table>
      )}
    </Card>
  );
}

export function Cash() {
  const { t, lang } = useI18n();
  const app = useApp();

  // The inline editor: which row, and what has been typed into it.
  const [editing, setEditing] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState<number | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  /** Which pot's history the log below is filtered to, or "all". */
  const [logAccount, setLogAccount] = useState<number | "all">("all");
  /** The pot money is being put into or taken out of, or null when closed. */
  const [entryFor, setEntryFor] = useState<CashAccount | null>(null);
  /** What the last entry did, for the one line of feedback after it. */
  const [entryDone, setEntryDone] = useState<string | null>(null);
  const [editRow, setEditRow] = useState<CashAccount | null>(null);
  const [editAttempted, setEditAttempted] = useState(false);
  const [editName, setEditName] = useState("");
  const [editNote, setEditNote] = useState("");

  const [busy, setBusy] = useState(false);

  const portfolio = app.portfolio;
  if (!portfolio) return <Spinner label={t("state.loading")} />;

  const base = app.baseCurrency;
  const rows = portfolio.cash;

  const subtotals = CURRENCIES.map((code) => {
    const held = rows.filter((row) => row.currency === code);
    return {
      code,
      count: held.length,
      amount: held.reduce((sum, row) => sum + row.balance, 0),
    };
  }).filter((entry) => entry.count > 0);

  const totalBase = rows.reduce((sum, row) => sum + (row.value_base ?? 0), 0);
  const leftOut = rows.filter((row) => row.value_base === null).length;

  const startEdit = (row: CashAccount) => {
    setEditing(row.id);
    setDraft(formatQuantity(row.balance, lang));
    setStatus(null);
  };

  const commit = async (row: CashAccount) => {
    const amount = parseAmount(draft, lang);
    if (amount === null || amount === row.balance) {
      setEditing(null);
      return;
    }
    setSaving(row.id);
    try {
      await updateCash(row.id, { balance: amount });
      // The dashboard total is the same money, so it is re-read rather than
      // left to disagree with this page.
      await app.refresh();
      setStatus(t("cash.balance_saved"));
      setEditing(null);
      setError(null);
    } catch (cause) {
      setError(messageOf(cause));
    } finally {
      setSaving(null);
    }
  };

  const openEdit = (row: CashAccount) => {
    setEditRow(row);
    setEditName(row.name);
    setEditNote(row.note ?? "");
    setEditAttempted(false);
  };

  const submitEdit = async () => {
    if (!editRow) return;
    setEditAttempted(true);
    if (!editName.trim()) return;
    setBusy(true);
    try {
      // The balance is deliberately not here: it is edited in place, and
      // renaming a pot must not restamp the day the money was counted. The
      // currency is not here either — it is the pot's identity.
      await updateCash(editRow.id, {
        name: editName.trim(),
        note: editNote.trim() || null,
      });
      await app.refresh();
      setEditRow(null);
      setError(null);
    } catch (cause) {
      setError(messageOf(cause));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      {error && (
        <Notice
          tone="error"
          title={t("form.save_failed")}
          onDismiss={() => setError(null)}
        >
          {error}
        </Notice>
      )}

      {entryDone && (
        <Notice tone="info" onDismiss={() => setEntryDone(null)}>
          {entryDone}
        </Notice>
      )}

      <Card title={t("cash.title")} subtitle={t("cash.manual_note")}>
        {status && (
          <div className="mb-3">
            <Badge tone="positive">{status}</Badge>
          </div>
        )}

        <Table
          head={
            <>
              <Th>{t("cash.name")}</Th>
              <Th>{t("field.currency")}</Th>
              <Th align="right">{t("cash.balance")}</Th>
              <Th>{t("cash.balance_at")}</Th>
              <Th align="right">{t("cash.value_in_base")}</Th>
              <Th>{t("cash.note")}</Th>
              <Th align="right">{t("hold.actions")}</Th>
            </>
          }
        >
          {rows.map((row) => (
            <tr key={row.id}>
              <Td>{row.name}</Td>
              <Td>
                <Badge tone="info">{t(`currency.${row.currency}` as const)}</Badge>
              </Td>
              <Td align="right">
                {editing === row.id ? (
                  <div className="flex items-center justify-end gap-1">
                    <Input
                      autoFocus
                      inputMode="decimal"
                      aria-label={t("cash.edit_balance")}
                      className="w-28 text-right"
                      value={draft}
                      onChange={(event) => setDraft(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.preventDefault();
                          void commit(row);
                        }
                        if (event.key === "Escape") {
                          event.preventDefault();
                          setEditing(null);
                        }
                      }}
                    />
                    <Button
                      size="sm"
                      variant="primary"
                      loading={saving === row.id}
                      onClick={() => void commit(row)}
                    >
                      {t("action.save")}
                    </Button>
                  </div>
                ) : (
                  <button
                    type="button"
                    title={t("cash.edit_balance")}
                    aria-label={t("cash.edit_balance")}
                    onClick={() => startEdit(row)}
                    className="rounded-md px-2 py-1 font-medium tabular-nums text-slate-900 underline decoration-dotted decoration-slate-300 underline-offset-4 hover:bg-slate-100"
                  >
                    {formatMoney(row.balance, row.currency, lang)}
                  </button>
                )}
              </Td>
              <Td>{formatDate(row.balance_at, lang)}</Td>
              <Td align="right">
                {row.value_base === null ? (
                  <Badge tone="warning">{t("reason.not_convertible")}</Badge>
                ) : (
                  formatMoney(row.value_base, base, lang)
                )}
              </Td>
              <Td>{row.note || DASH}</Td>
              <Td align="right">
                <div className="flex flex-wrap justify-end gap-1">
                  <Button
                    size="sm"
                    variant="primary"
                    onClick={() => {
                      setEntryDone(null);
                      setEntryFor(row);
                    }}
                  >
                    {t("cash.add_entry")}
                  </Button>
                  <Button size="sm" onClick={() => openEdit(row)}>
                    {t("action.edit")}
                  </Button>
                  <Button size="sm" onClick={() => setLogAccount(row.id)}>
                    {t("cash.move_history")}
                  </Button>
                </div>
              </Td>
            </tr>
          ))}
        </Table>
      </Card>

      <Card title={t("cash.subtotal")}>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {subtotals.map((entry) => (
            <Stat
              key={entry.code}
              label={t(`currency.${entry.code}` as const)}
              value={formatMoney(entry.amount, entry.code, lang)}
            />
          ))}
          <Stat
            label={t("cash.total")}
            value={formatMoney(totalBase, base, lang)}
            tone={leftOut > 0 ? "warning" : "neutral"}
          />
        </div>
        {leftOut > 0 && (
          <div className="mt-3">
            <Badge tone="warning">{t("state.not_counted")}</Badge>
          </div>
        )}
      </Card>

      <MovementsCard
        accounts={rows}
        movements={app.portfolio?.movements ?? []}
        account={logAccount}
        onAccount={setLogAccount}
      />

      {entryFor !== null && (
        <EntryForm
          account={entryFor}
          onClose={() => setEntryFor(null)}
          onDone={(message) => {
            setEntryFor(null);
            setEntryDone(message);
            setError(null);
          }}
        />
      )}

      <Modal
        open={editRow !== null}
        title={t("cash.edit_title")}
        onClose={() => setEditRow(null)}
        footer={
          <>
            <Button onClick={() => setEditRow(null)}>{t("action.cancel")}</Button>
            <Button
              variant="primary"
              loading={busy}
              onClick={() => void submitEdit()}
            >
              {t("action.save")}
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <Input
            autoFocus
            label={t("cash.name")}
            value={editName}
            onChange={(event) => setEditName(event.target.value)}
            error={
              editAttempted && !editName.trim() ? t("form.required") : undefined
            }
          />
          <Textarea
            label={`${t("cash.note")} (${t("state.optional")})`}
            value={editNote}
            onChange={(event) => setEditNote(event.target.value)}
          />
        </div>
      </Modal>

    </div>
  );
}

export default Cash;
