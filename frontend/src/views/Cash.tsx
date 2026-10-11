/**
 * Cash: a balance you write down, edited where it is shown.
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

import { createCash, deleteCash, updateCash } from "../api/client";
import type { CashAccount, Currency, Lang } from "../api/types";
import {
  CURRENCIES,
  DASH,
  formatDate,
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

/** The two currencies this app can hold; a third is never offered. */
function CurrencySelect({
  value,
  onChange,
  hint,
}: {
  value: Currency;
  onChange: (code: Currency) => void;
  hint?: string;
}) {
  const { t } = useI18n();
  return (
    <Select
      label={t("field.currency")}
      hint={hint}
      value={value}
      onChange={(event) => {
        // Looked up in the closed set rather than cast: whatever the DOM says,
        // only a currency this app can hold gets through.
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

function messageOf(cause: unknown): string {
  if (cause instanceof Error) return cause.message;
  return String(cause);
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

  const [addOpen, setAddOpen] = useState(false);
  const [addAttempted, setAddAttempted] = useState(false);
  const [addName, setAddName] = useState("");
  const [addCurrency, setAddCurrency] = useState<Currency>("VND");
  const [addBalance, setAddBalance] = useState("");
  const [addNote, setAddNote] = useState("");

  const [editRow, setEditRow] = useState<CashAccount | null>(null);
  const [editAttempted, setEditAttempted] = useState(false);
  const [editName, setEditName] = useState("");
  const [editCurrency, setEditCurrency] = useState<Currency>("VND");
  const [editNote, setEditNote] = useState("");

  const [removeRow, setRemoveRow] = useState<CashAccount | null>(null);
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

  const openAdd = () => {
    setAddName("");
    setAddCurrency(base);
    setAddBalance("");
    setAddNote("");
    setAddAttempted(false);
    setAddOpen(true);
  };

  const submitAdd = async () => {
    setAddAttempted(true);
    const amount = parseAmount(addBalance, lang);
    if (!addName.trim() || amount === null) return;
    setBusy(true);
    try {
      await createCash({
        name: addName.trim(),
        currency: addCurrency,
        balance: amount,
        note: addNote.trim() || null,
      });
      await app.refresh();
      setAddOpen(false);
      setError(null);
    } catch (cause) {
      setError(messageOf(cause));
    } finally {
      setBusy(false);
    }
  };

  const openEdit = (row: CashAccount) => {
    setEditRow(row);
    setEditName(row.name);
    setEditCurrency(row.currency);
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
      // renaming an account must not restamp the day the money was counted.
      await updateCash(editRow.id, {
        name: editName.trim(),
        currency: editCurrency,
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

  const confirmDelete = async () => {
    if (!removeRow) return;
    setBusy(true);
    try {
      await deleteCash(removeRow.id);
      await app.refresh();
      setRemoveRow(null);
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

      <Card
        title={t("cash.title")}
        subtitle={t("cash.manual_note")}
        actions={
          <Button variant="primary" onClick={openAdd}>
            {t("cash.add")}
          </Button>
        }
      >
        {status && (
          <div className="mb-3">
            <Badge tone="positive">{status}</Badge>
          </div>
        )}

        {rows.length === 0 ? (
          <EmptyState
            title={t("cash.none_title")}
            body={t("cash.none_body")}
            action={
              <Button variant="primary" onClick={openAdd}>
                {t("cash.add")}
              </Button>
            }
          />
        ) : (
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
                  <div className="flex justify-end gap-1">
                    <Button size="sm" onClick={() => openEdit(row)}>
                      {t("action.edit")}
                    </Button>
                    <Button size="sm" onClick={() => setRemoveRow(row)}>
                      {t("action.delete")}
                    </Button>
                  </div>
                </Td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      {rows.length > 0 && (
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
      )}

      <Modal
        open={addOpen}
        title={t("cash.add")}
        onClose={() => setAddOpen(false)}
        footer={
          <>
            <Button onClick={() => setAddOpen(false)}>{t("action.cancel")}</Button>
            <Button
              variant="primary"
              loading={busy}
              onClick={() => void submitAdd()}
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
            value={addName}
            onChange={(event) => setAddName(event.target.value)}
            error={
              addAttempted && !addName.trim() ? t("form.required") : undefined
            }
          />
          <CurrencySelect
            value={addCurrency}
            onChange={setAddCurrency}
            hint={t("form.currency_hint")}
          />
          <NumberInput
            label={t("cash.balance")}
            placeholder={formatQuantity(0, lang)}
            value={addBalance}
            onValueChange={setAddBalance}
            error={
              addAttempted && parseAmount(addBalance, lang) === null
                ? t("form.required")
                : undefined
            }
          />
          <Textarea
            label={t("cash.note")}
            hint={t("state.optional")}
            value={addNote}
            onChange={(event) => setAddNote(event.target.value)}
          />
        </div>
      </Modal>

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
          <CurrencySelect
            value={editCurrency}
            onChange={setEditCurrency}
            hint={t("form.currency_hint")}
          />
          <Textarea
            label={t("cash.note")}
            hint={t("state.optional")}
            value={editNote}
            onChange={(event) => setEditNote(event.target.value)}
          />
        </div>
      </Modal>

      <Modal
        open={removeRow !== null}
        title={t("action.delete")}
        onClose={() => setRemoveRow(null)}
        footer={
          <>
            <Button onClick={() => setRemoveRow(null)}>{t("action.cancel")}</Button>
            <Button
              variant="danger"
              loading={busy}
              onClick={() => void confirmDelete()}
            >
              {t("action.delete")}
            </Button>
          </>
        }
      >
        <p>{t("cash.delete_confirm", { name: removeRow?.name ?? "" })}</p>
      </Modal>
    </div>
  );
}

export default Cash;
