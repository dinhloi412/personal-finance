/**
 * The positions table: what is held, what it is worth, and what is missing.
 *
 * The one idea this page is built around is that `reason` is not a decoration.
 * A position can be missing its value (no price yet, a quote in a currency this
 * app cannot convert, a quantity of zero) or missing only its cost. Those are
 * different situations and they are answered in different cells:
 *
 * - a missing VALUE puts the reason in the value cell, in place of the number,
 *   and marks the row as not counted — because that is exactly what happened;
 * - a missing COST leaves a value the app does know, so the reason goes in the
 *   gain cell, where the gap actually is. Printing it over the value would hide
 *   a figure that is known, which is the opposite of honest.
 *
 * Filtering is done here rather than by the server: the whole portfolio is
 * already in context, so the table re-filters on every keystroke with no
 * request, and stays consistent with the totals on the Dashboard.
 */

import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

import {
  createAsset,
  deleteAsset,
  deleteRealized,
  priceAsset,
  sellAsset,
  updateAsset,
} from "../api/client";
import type {
  Asset,
  AssetInput,
  AssetPatch,
  AssetSale,
  CashMoveOut,
  Currency,
  MarketKind,
  Realized,
  UnpricedReason,
} from "../api/types";
import { CashMoveFields, CashMoveNotice } from "../components/CashMove";
import { InstrumentPicker } from "../components/InstrumentPicker";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  IconButton,
  Input,
  Modal,
  Notice,
  NumberInput,
  Select,
  SlideOver,
  Spinner,
  Table,
  Td,
  Textarea,
  Th,
} from "../components/ui";
import {
  CURRENCIES,
  formatDate,
  formatMoney,
  formatPercent,
  formatQuantity,
  formatSignedMoney,
  useLang,
  useT,
} from "../i18n";
import { useApp } from "../state/AppContext";

/** What may be held as a market position. Cash has its own page, and no price. */
const KINDS: MarketKind[] = ["stock", "fund", "crypto"];

/** The filter adds "all" to the same list, so the two can never drift apart. */
const FILTER_KINDS: (MarketKind | "all")[] = ["all", ...KINDS];

/**
 * A number typed by a person, or null when it is not one yet.
 *
 * A comma is accepted as the decimal mark because that is the key a Vietnamese
 * keyboard has, and reading "1,5" as 1 would be a silent tenfold error in a
 * quantity. Anything still unreadable returns null, which disables the save
 * button rather than storing a wrong number.
 */
function toNumber(text: string): number | null {
  const cleaned = text.trim().replace(/\s/g, "").replace(",", ".");
  if (cleaned === "") return null;
  const value = Number(cleaned);
  return Number.isFinite(value) ? value : null;
}

/**
 * One slide-over, used for both adding and editing.
 *
 * It is mounted only while it is open, so the initial state below is also the
 * "reset" — there is no stale form to clear when the next position is opened.
 */
function PositionForm({
  asset,
  onClose,
  onSaved,
}: {
  /** The position being edited, or null when adding a new one. */
  asset: Asset | null;
  onClose: () => void;
  /** The row as the server stored it, so the page can report the cash side. */
  onSaved: (saved: Asset) => void;
}) {
  const t = useT();
  const app = useApp();

  const [symbol, setSymbol] = useState(asset?.symbol ?? "");
  const [kind, setKind] = useState<MarketKind>(asset?.kind ?? "stock");
  const [name, setName] = useState(asset?.name ?? "");
  const [quantity, setQuantity] = useState(asset ? String(asset.quantity) : "");
  const [costBasis, setCostBasis] = useState(
    asset?.cost_basis === null || asset?.cost_basis === undefined
      ? ""
      : String(asset.cost_basis),
  );
  const [currency, setCurrency] = useState<Currency>(
    asset?.currency ?? app.baseCurrency,
  );
  const [note, setNote] = useState(asset?.note ?? "");
  const [cashAmount, setCashAmount] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const quantityValue = toNumber(quantity);
  const costValue = costBasis.trim() === "" ? null : toNumber(costBasis);
  const costInvalid = costBasis.trim() !== "" && costValue === null;
  const symbolOk = symbol.trim() !== "";
  const quantityOk = quantityValue !== null && quantityValue >= 0;
  const canSave = symbolOk && quantityOk && !costInvalid && !saving;

  const submit = async () => {
    if (!canSave || quantityValue === null) return;

    const cleanedSymbol = symbol.trim().toUpperCase();
    const typedName = name.trim();
    // `assets.name` is NOT NULL, so a blank field means "call it by its
    // symbol" rather than "store nothing" — the same substitution the server
    // makes when a position is created without a name.
    const effectiveName = typedName === "" ? cleanedSymbol : typedName;

    const input: AssetInput = {
      symbol: cleanedSymbol,
      kind,
      name: effectiveName,
      quantity: quantityValue,
      cost_basis: costValue,
      currency,
      note: note.trim() === "" ? null : note.trim(),
      // Only sent when the user is adding a position or changing what it cost:
      // a quantity correction is not a purchase, and the server moves nothing
      // for one. See `app.routers.assets.update_asset`.
      cash_amount:
        asset === null || (costValue ?? null) !== asset.cost_basis
          ? toNumber(cashAmount)
          : null,
    };

    setSaving(true);
    setError(null);
    try {
      if (asset === null) {
        const created = await createAsset(input);
        onSaved(created);
      } else {
        // Only what changed. A PATCH that resends every field would rewrite the
        // ones the user never touched, and would make an accidental edit of an
        // unrelated value impossible to spot in the request log.
        const patch: AssetPatch = {};
        if (input.symbol !== asset.symbol) patch.symbol = input.symbol;
        if (input.kind !== asset.kind) patch.kind = input.kind;
        if (effectiveName !== asset.name) patch.name = effectiveName;
        if (input.quantity !== asset.quantity) patch.quantity = input.quantity;
        if ((input.cost_basis ?? null) !== asset.cost_basis) {
          patch.cost_basis = input.cost_basis;
        }
        if (input.currency !== asset.currency) patch.currency = input.currency;
        if ((input.note ?? null) !== asset.note) patch.note = input.note;

        if (Object.keys(patch).length > 0) {
          onSaved(await updateAsset(asset.id, patch));
        }
      }
      await app.refresh();
      onClose();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setSaving(false);
    }
  };

  return (
    <SlideOver
      open
      title={asset === null ? t("form.add_title") : t("form.edit_title")}
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose} disabled={saving}>
            {t("action.cancel")}
          </Button>
          <Button
            variant="primary"
            loading={saving}
            disabled={!canSave}
            onClick={() => {
              void submit();
            }}
          >
            {t("action.save")}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <InstrumentPicker
          value={symbol}
          onChange={setSymbol}
          kind={kind}
          onPick={(suggestion) => {
            // A picked suggestion fills in what the feed knows; the symbol
            // itself was already reported by `onChange`.
            if (suggestion.name) setName(suggestion.name);
            if (
              suggestion.kind === "stock" ||
              suggestion.kind === "fund" ||
              suggestion.kind === "crypto"
            ) {
              setKind(suggestion.kind);
            }
            if (suggestion.currency === "VND" || suggestion.currency === "USD") {
              setCurrency(suggestion.currency);
            }
          }}
        />

        <Select
          label={t("form.kind")}
          value={kind}
          onChange={(event) => setKind(event.target.value as MarketKind)}
        >
          {KINDS.map((option) => (
            <option key={option} value={option}>
              {t(`kind.${option}` as const)}
            </option>
          ))}
        </Select>

        <Input
          label={`${t("form.name")} (${t("state.optional")})`}
          value={name}
          onChange={(event) => setName(event.target.value)}
        />

        <NumberInput
          label={t("form.quantity")}
          value={quantity}
          onValueChange={setQuantity}
          error={quantity !== "" && !quantityOk ? t("form.required") : undefined}
        />

        {/* Left blank, the gain cannot be shown — the hint says so, in the
            wording the whole app uses for an unknown figure. */}
        <NumberInput
          label={`${t("form.cost_basis")} (${t("state.optional")})`}
          hint={t("form.cost_basis_hint")}
          value={costBasis}
          onValueChange={setCostBasis}
          error={costInvalid ? t("form.required") : undefined}
        />

        <Select
          label={t("form.currency")}
          hint={t("form.currency_hint")}
          value={currency}
          onChange={(event) => setCurrency(event.target.value as Currency)}
        >
          {CURRENCIES.map((code) => (
            <option key={code} value={code}>
              {t(`currency.${code}` as const)}
            </option>
          ))}
        </Select>

        {/* Where the money comes from, when the user has asked for trades to
            move cash. Nothing on an edit: the difference is moved for them, to
            the account that paid — see the note below. */}
        {asset === null ? (
          <CashMoveFields
            direction="out"
            amount={costValue}
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

        {error && (
          <Notice tone="error" title={t("form.save_failed")}>
            {error}
          </Notice>
        )}
      </div>
    </SlideOver>
  );
}

/**
 * The sell form: how much went, and how much came back.
 *
 * Two facts, because they are the only two the app cannot look up. What was
 * received is deliberately NOT pre-filled from the current price: a sale
 * recorded at the market's number would print the position's *unrealised* gain
 * as a realised one, which is the exact confusion this form exists to remove.
 * The market value of the part being sold is shown beside the field as a
 * reference, and the user types what actually arrived.
 *
 * The currency is not a field either. Money from a sale arrives in the market's
 * currency for that symbol — the currency its price is quoted in — and offering
 * a choice would be offering to record dollars as dong.
 */
function SellForm({
  asset,
  onClose,
  onSold,
}: {
  asset: Asset;
  onClose: () => void;
  /** The recorded sale, so the page can say what it locked in — and where the
   * money went, if the cash link is on. */
  onSold: (sale: Realized) => void;
}) {
  const t = useT();
  const lang = useLang();
  const app = useApp();

  /** Where the money arrives: the quote's currency, or the position's own when
   * nothing was ever quoted. The server decides the same way. */
  const currency = asset.price_currency ?? asset.currency;

  const [quantity, setQuantity] = useState(String(asset.quantity));
  const [proceeds, setProceeds] = useState("");
  // Today, in UTC, which is the day the server would write if the field were
  // left alone — so an untouched field and an omitted one agree.
  const [soldOn, setSoldOn] = useState(new Date().toISOString().slice(0, 10));
  const [note, setNote] = useState("");
  const [cashAmount, setCashAmount] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const quantityValue = toNumber(quantity);
  const proceedsValue = toNumber(proceeds);
  // A hair above what is held is accepted, because the field is pre-filled with
  // the held quantity and a float may come back a digit below it. The server
  // makes the same allowance and treats it as a full sale.
  const quantityOk =
    quantityValue !== null &&
    quantityValue > 0 &&
    quantityValue <= asset.quantity + 1e-9;
  const proceedsOk = proceedsValue !== null && proceedsValue >= 0;
  const canSave = quantityOk && proceedsOk && !saving;

  const reference =
    quantityOk && quantityValue !== null && asset.price !== null
      ? quantityValue * asset.price
      : null;

  // "Not a number yet" and "more than you hold" are different mistakes, and the
  // field says which rather than blaming the quantity for being unreadable. An
  // untouched field is neither: it is empty, and the button is simply off.
  let quantityError: string | undefined;
  if (quantity !== "" && quantityValue === null) {
    quantityError = t("form.invalid");
  } else if (quantityValue !== null && !quantityOk) {
    quantityError = t("sell.too_many");
  }

  const proceedsError =
    proceeds !== "" && !proceedsOk ? t("form.invalid") : undefined;

  const submit = async () => {
    if (!canSave || quantityValue === null || proceedsValue === null) return;

    const body: AssetSale = {
      quantity: quantityValue,
      proceeds: proceedsValue,
      sold_on: soldOn || undefined,
      note: note.trim() === "" ? null : note.trim(),
      cash_amount: toNumber(cashAmount),
    };

    setSaving(true);
    setError(null);
    try {
      const sale = await sellAsset(asset.id, body);
      await app.refresh();
      onSold(sale);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setSaving(false);
    }
  };

  return (
    <SlideOver
      open
      title={t("sell.title", { symbol: asset.symbol })}
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose} disabled={saving}>
            {t("action.cancel")}
          </Button>
          <Button
            variant="primary"
            loading={saving}
            disabled={!canSave}
            onClick={() => {
              void submit();
            }}
          >
            {t("sell.confirm")}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <NumberInput
          label={t("sell.quantity")}
          hint={t("sell.quantity_hint", {
            quantity: formatQuantity(asset.quantity, lang),
          })}
          value={quantity}
          onValueChange={setQuantity}
          error={quantityError}
        />

        <div>
          <Button
            size="sm"
            variant="subtle"
            onClick={() => setQuantity(String(asset.quantity))}
          >
            {t("sell.all")}
          </Button>
        </div>

        <NumberInput
          label={t("sell.proceeds")}
          hint={t("sell.proceeds_hint", { currency })}
          value={proceeds}
          onValueChange={setProceeds}
          error={proceedsError}
          disabled={saving}
        />

        {/* What the market says that part is worth — a reference to compare
            against what was actually received, never entered on the user's
            behalf. In the quote's own currency, so no conversion is involved. */}
        {reference !== null && (
          <p className="-mt-2 text-xs text-slate-500">
            {t("sell.market_hint", {
              amount: formatMoney(reference, currency, lang),
            })}
          </p>
        )}

        <Input
          type="date"
          label={t("sell.sold_on")}
          value={soldOn}
          onChange={(event) => setSoldOn(event.target.value)}
        />

        {/* What came back, and the pot it goes into when the user has asked
            trades to move cash: the pot of the sale's own currency. */}
        <CashMoveFields
          direction="in"
          amount={proceedsOk ? proceedsValue : null}
          currency={currency}
          cashAmount={cashAmount}
          onCashAmount={setCashAmount}
        />

        <Notice tone="info">{t("sell.cost_note")}</Notice>

        {/* A position with no cost basis has no computable gain, and the user
            should know that before the sale is recorded rather than after. */}
        {asset.cost_basis === null && (
          <Notice tone="warning">{t("sell.no_cost")}</Notice>
        )}

        <Textarea
          label={`${t("form.note")} (${t("state.optional")})`}
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />

        {error && (
          <Notice tone="error" title={t("sell.failed")}>
            {error}
          </Notice>
        )}
      </div>
    </SlideOver>
  );
}

/** One entry of a row's action menu. */
function MenuButton({
  tone = "neutral",
  onClick,
  children,
}: {
  tone?: "neutral" | "danger";
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`block w-full px-3 py-2 text-left text-sm transition-colors ${
        tone === "danger"
          ? "text-rose-600 hover:bg-rose-50"
          : "text-slate-700 hover:bg-slate-50"
      }`}
    >
      {children}
    </button>
  );
}

/**
 * What has already been sold.
 *
 * This is not a ledger and not a history of the portfolio: it is the four
 * figures of each closed trade, kept because the dashboard prints one realised
 * total and a total nobody can open is a total nobody can check. Deleting a row
 * is the way back from a sale entered by mistake — and the only way, because
 * the shares are gone and this app cannot invent them.
 */
function SoldPositions({ onDelete }: { onDelete: (sale: Realized) => void }) {
  const t = useT();
  const lang = useLang();
  const app = useApp();
  const base = app.baseCurrency;

  const sales = app.portfolio?.realized ?? [];
  const realizedGain = app.portfolio?.realized_gain ?? null;
  if (sales.length === 0) return null;

  const reasonText = (reason: UnpricedReason | null) =>
    reason === null ? t("state.unknown") : t(`reason.${reason}` as const);

  return (
    <Card title={t("hold.realized_title")} subtitle={t("hold.realized_hint")}>
      <Table
        head={
          <>
            <Th>{t("hold.symbol")}</Th>
            <Th align="right">{t("hold.sold_on")}</Th>
            <Th align="right">{t("hold.quantity")}</Th>
            <Th align="right">{t("hold.proceeds")}</Th>
            <Th align="right">{t("hold.cost_removed")}</Th>
            <Th align="right">{t("hold.gain")}</Th>
            <Th align="right">{t("hold.gain_pct")}</Th>
            <Th align="right">{t("hold.actions")}</Th>
          </>
        }
      >
        {sales.map((sale) => (
          <tr key={sale.id}>
            <Td>
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium text-slate-900">{sale.symbol}</span>
                <Badge>{t(`kind.${sale.kind}` as const)}</Badge>
              </div>
              <div className="text-xs text-slate-500">{sale.name}</div>
              {/* The note is free text the user typed at the time — a dividend,
                  a reason, a broker. It reads as a caption under the name. */}
              {sale.note && (
                <div className="text-xs text-slate-400">{sale.note}</div>
              )}
            </Td>

            <Td align="right" className="whitespace-nowrap tabular-nums text-slate-500">
              {formatDate(sale.sold_on, lang)}
            </Td>

            <Td align="right" className="tabular-nums">
              {formatQuantity(sale.quantity, lang)}
            </Td>

            {/* Both sides are shown in the base currency, because that is the
                only figure comparable across the row — with the amount as it
                was actually received underneath when that was in another
                currency. */}
            <Td align="right" className="tabular-nums">
              <div className="font-medium text-slate-900">
                {formatMoney(sale.proceeds_base, base, lang)}
              </div>
              {sale.proceeds_currency !== base && (
                <div className="text-xs text-slate-500">
                  {formatMoney(sale.proceeds, sale.proceeds_currency, lang)}
                </div>
              )}
            </Td>

            <Td align="right" className="tabular-nums">
              {sale.cost_base === null ? (
                <Badge tone="warning">{reasonText(sale.reason)}</Badge>
              ) : (
                <>
                  <div>{formatMoney(sale.cost_base, base, lang)}</div>
                  {sale.currency !== base && sale.cost_removed !== null && (
                    <div className="text-xs text-slate-500">
                      {formatMoney(sale.cost_removed, sale.currency, lang)}
                    </div>
                  )}
                </>
              )}
            </Td>

            <Td align="right" className="tabular-nums">
              {sale.gain === null ? (
                <Badge tone="warning">{reasonText(sale.reason)}</Badge>
              ) : (
                <span
                  className={
                    sale.gain === 0
                      ? ""
                      : sale.gain > 0
                        ? "text-emerald-600"
                        : "text-rose-600"
                  }
                >
                  {formatSignedMoney(sale.gain, base, lang)}
                </span>
              )}
            </Td>

            <Td align="right" className="tabular-nums">
              {formatPercent(sale.gain_pct, lang)}
            </Td>

            <Td align="right">
              <Button size="sm" onClick={() => onDelete(sale)}>
                {t("action.delete")}
              </Button>
            </Td>
          </tr>
        ))}
      </Table>

      <div className="mt-4 flex flex-wrap items-baseline gap-x-6 gap-y-1 border-t border-slate-100 pt-3 text-sm">
        <span className="text-slate-500">{t("dash.realized")}</span>
        {realizedGain === null ? (
          <span className="text-xs text-slate-500">
            {t("dash.realized_unknown")}
          </span>
        ) : (
          <span
            className={`font-medium tabular-nums ${
              realizedGain === 0
                ? "text-slate-900"
                : realizedGain > 0
                  ? "text-emerald-600"
                  : "text-rose-600"
            }`}
          >
            {formatSignedMoney(realizedGain, base, lang)}
          </span>
        )}
      </div>
    </Card>
  );
}

export function Holdings() {
  const t = useT();
  const lang = useLang();
  const app = useApp();
  const base = app.baseCurrency;

  const [kindFilter, setKindFilter] = useState<MarketKind | "all">("all");
  const [query, setQuery] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Asset | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Asset | null>(null);
  /** The position being sold, or null when the sell form is closed. */
  const [selling, setSelling] = useState<Asset | null>(null);
  /** What the last sale locked in, for the one line of feedback after it. */
  const [justSold, setJustSold] = useState<Realized | null>(null);
  /** What the last trade did to a cash balance, or why it did nothing. */
  const [cashNotice, setCashNotice] = useState<CashMoveOut | null>(null);
  const [saleToDelete, setSaleToDelete] = useState<Realized | null>(null);
  const [menu, setMenu] = useState<{
    id: number;
    right: number;
    top?: number;
    bottom?: number;
  } | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  // A click anywhere else, a scroll or a resize closes the open menu. The menu
  // is pinned to the viewport rather than to its cell, so it would otherwise be
  // left pointing at a row that has moved out from under it.
  useEffect(() => {
    if (menu === null) return undefined;
    const close = () => setMenu(null);
    const onDocumentDown = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        close();
      }
    };
    globalThis.document.addEventListener("mousedown", onDocumentDown);
    globalThis.addEventListener("scroll", close, true);
    globalThis.addEventListener("resize", close);
    return () => {
      globalThis.document.removeEventListener("mousedown", onDocumentDown);
      globalThis.removeEventListener("scroll", close, true);
      globalThis.removeEventListener("resize", close);
    };
  }, [menu]);

  /**
   * Where to pin the menu, in viewport coordinates.
   *
   * The table scrolls horizontally and a scroll container clips whatever leaves
   * it, so an absolutely positioned menu in the last column is cut off by the
   * card. It opens from the button's right edge — never past the right of the
   * screen — and downwards when there is more room below than above, which
   * keeps it on screen for the last row as well as the first.
   */
  const anchorMenu = (id: number, button: HTMLElement) => {
    const rect = button.getBoundingClientRect();
    // Measured against the viewport a fixed element is positioned in, which is
    // the document's client box — the scrollbar is not part of it.
    const viewport = globalThis.document.documentElement;
    const right = viewport.clientWidth - rect.right;
    const below = viewport.clientHeight - rect.bottom;
    return below < rect.top
      ? { id, right, bottom: viewport.clientHeight - rect.top + 4 }
      : { id, right, top: rect.bottom + 4 };
  };

  const assets = app.portfolio?.assets ?? [];
  const needle = query.trim().toLowerCase();
  const filtered = assets.filter((asset) => {
    if (kindFilter !== "all" && asset.kind !== kindFilter) return false;
    if (needle === "") return true;
    return (
      asset.symbol.toLowerCase().includes(needle) ||
      asset.name.toLowerCase().includes(needle)
    );
  });

  // Rows that could not be converted have no base value; they contribute
  // nothing here and say so in their own cell.
  const totalBase = filtered.reduce(
    (sum, asset) => sum + (asset.value_base ?? 0),
    0,
  );

  const reasonText = (reason: UnpricedReason | null) =>
    reason === null ? t("state.unknown") : t(`reason.${reason}` as const);

  if (app.portfolio === null) {
    return (
      <Card>
        <Spinner label={t("state.loading")} />
      </Card>
    );
  }

  const onDelete = async () => {
    if (deleteTarget === null) return;
    setBusyId(deleteTarget.id);
    setActionError(null);
    try {
      const removed = await deleteAsset(deleteTarget.id);
      await app.refresh();
      setCashNotice(removed.cash);
      setDeleteTarget(null);
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusyId(null);
    }
  };

  const onPriceOne = async (target: Asset) => {
    setMenu(null);
    setBusyId(target.id);
    setActionError(null);
    try {
      await priceAsset(target.id);
      await app.refresh();
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusyId(null);
    }
  };

  const openAdd = () => {
    setEditing(null);
    setCashNotice(null);
    setFormOpen(true);
  };

  /** Forget one recorded sale. The position it closed is not restored — the
   * confirmation in front of this says so. */
  const onDeleteSale = async () => {
    if (saleToDelete === null) return;
    setActionError(null);
    try {
      await deleteRealized(saleToDelete.id);
      await app.refresh();
      setSaleToDelete(null);
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : String(cause));
    }
  };

  return (
    <div className="space-y-4">
      {actionError && (
        <Notice tone="error" title={t("state.error")}>
          {actionError}
        </Notice>
      )}

      {/* The sale is confirmed with what it locked in, not with a bare "saved":
          the gain is the whole reason the row exists, and it is the one number
          the user cannot check from the positions table — the position is gone
          from there. */}
      {justSold !== null && (
        <Notice tone="info">
          {justSold.gain === null
            ? `${t("sell.done", { symbol: justSold.symbol })} · ${t("dash.realized_unknown")}`
            : `${t("sell.done", { symbol: justSold.symbol })} · ${t("dash.realized")} ${formatSignedMoney(justSold.gain, base, lang)}`}
        </Notice>
      )}

      <CashMoveNotice cash={cashNotice} />

      <Card
        title={t("hold.title")}
        actions={
          <Button size="sm" variant="primary" onClick={openAdd}>
            {t("hold.add")}
          </Button>
        }
      >
        <div className="mb-4 flex flex-wrap items-end gap-4">
          <div className="w-36">
            <Select
              label={t("hold.kind")}
              value={kindFilter}
              onChange={(event) =>
                setKindFilter(event.target.value as MarketKind | "all")
              }
            >
              {FILTER_KINDS.map((option) => (
                <option key={option} value={option}>
                  {t(`kind.${option}` as const)}
                </option>
              ))}
            </Select>
          </div>
          <div className="min-w-56 flex-1">
            <Input
              label={t("hold.search")}
              placeholder={t("hold.search_placeholder")}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
        </div>

        {assets.length === 0 ? (
          <EmptyState
            title={t("hold.none_title")}
            body={t("hold.none_body")}
            action={
              <Button variant="primary" onClick={openAdd}>
                {t("hold.add")}
              </Button>
            }
          />
        ) : filtered.length === 0 ? (
          <EmptyState title={t("hold.none_filtered")} />
        ) : (
          <>
            <Table
              head={
                <>
                  <Th>{t("hold.symbol")}</Th>
                  <Th align="right">{t("hold.quantity")}</Th>
                  <Th>{t("hold.kind")}</Th>
                  <Th align="right">{t("hold.price")}</Th>
                  <Th align="right">{t("hold.price_date")}</Th>
                  <Th align="right">{t("hold.value")}</Th>
                  <Th align="right">{t("hold.cost")}</Th>
                  <Th align="right">{t("hold.gain")}</Th>
                  <Th align="right">{t("hold.gain_pct")}</Th>
                  <Th align="right">{t("hold.actions")}</Th>
                </>
              }
            >
              {filtered.map((asset) => {
                // `value_base` is the only figure allowed into a total, so it
                // is also the one that decides whether a row is counted.
                const counted = asset.value_base !== null;
                const priceCurrency = asset.price_currency ?? asset.currency;
                return (
                  <tr
                    key={asset.id}
                    className={counted ? "" : "bg-amber-50/40"}
                  >
                    <Td>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium text-slate-900">
                          {asset.symbol}
                        </span>
                        {!counted && (
                          <Badge tone="warning">{t("state.not_counted")}</Badge>
                        )}
                      </div>
                      <div className="text-xs text-slate-500">{asset.name}</div>
                    </Td>

                    <Td align="right" className="tabular-nums">
                      {formatQuantity(asset.quantity, lang)}
                    </Td>

                    <Td>
                      <Badge>{t(`kind.${asset.kind}` as const)}</Badge>
                    </Td>

                    {/* The price keeps its own currency, and the session it
                        belongs to gets its own column: a price without its day
                        is not a fact, and a second line squeezed under the
                        number reads as a stray caption rather than as a
                        column. The two columns sit together, so the price and
                        its day are still read as one fact. */}
                    <Td align="right" className="whitespace-nowrap tabular-nums">
                      {formatMoney(asset.price, priceCurrency, lang)}
                    </Td>

                    <Td
                      align="right"
                      className="whitespace-nowrap tabular-nums text-slate-500"
                    >
                      {formatDate(asset.price_as_of, lang)}
                    </Td>

                    <Td align="right" className="tabular-nums">
                      {counted ? (
                        <span className="font-medium text-slate-900">
                          {formatMoney(asset.value_base, base, lang)}
                        </span>
                      ) : (
                        <Badge tone="warning">{reasonText(asset.reason)}</Badge>
                      )}
                    </Td>

                    <Td align="right" className="tabular-nums">
                      {formatMoney(asset.cost_base, base, lang)}
                    </Td>

                    <Td align="right" className="tabular-nums">
                      {asset.gain === null && asset.reason !== null ? (
                        <Badge tone="warning">{reasonText(asset.reason)}</Badge>
                      ) : (
                        formatSignedMoney(asset.gain, base, lang)
                      )}
                    </Td>

                    <Td align="right" className="tabular-nums">
                      {formatPercent(asset.gain_pct, lang)}
                    </Td>

                    <Td align="right">
                      <div ref={menu?.id === asset.id ? menuRef : null}>
                        <IconButton
                          label={t("hold.actions")}
                          className="border border-slate-300 bg-white hover:bg-slate-50"
                          disabled={busyId === asset.id}
                          onClick={(event) => {
                            if (menu?.id === asset.id) {
                              setMenu(null);
                              return;
                            }
                            setMenu(anchorMenu(asset.id, event.currentTarget));
                          }}
                        >
                          {/* Three dots drawn rather than typed: the glyph is
                              set at a size and height the surrounding text
                              decides, which is how a control stops looking
                              like one. */}
                          <svg
                            aria-hidden="true"
                            viewBox="0 0 16 16"
                            className="h-4 w-4 fill-current"
                          >
                            <circle cx="3" cy="8" r="1.5" />
                            <circle cx="8" cy="8" r="1.5" />
                            <circle cx="13" cy="8" r="1.5" />
                          </svg>
                        </IconButton>

                        {menu?.id === asset.id && (
                          // Positioned against the viewport so the table's own
                          // scroll container cannot clip it, and against the
                          // button's right edge so it can never leave the card.
                          <div
                            className="fixed z-40 w-48 overflow-hidden rounded-xl border border-slate-200 bg-white py-1 text-left shadow-lg"
                            style={{
                              right: menu.right,
                              top: menu.top,
                              bottom: menu.bottom,
                            }}
                          >
                            <MenuButton
                              onClick={() => {
                                setMenu(null);
                                setEditing(asset);
                                setFormOpen(true);
                              }}
                            >
                              {t("action.edit")}
                            </MenuButton>
                            <MenuButton
                              onClick={() => {
                                setMenu(null);
                                setSelling(asset);
                                setJustSold(null);
                              }}
                            >
                              {t("action.sell")}
                            </MenuButton>
                            <MenuButton
                              onClick={() => {
                                void onPriceOne(asset);
                              }}
                            >
                              {t("hold.price_now")}
                            </MenuButton>
                            <MenuButton
                              tone="danger"
                              onClick={() => {
                                setMenu(null);
                                setDeleteTarget(asset);
                              }}
                            >
                              {t("action.delete")}
                            </MenuButton>
                          </div>
                        )}
                      </div>
                    </Td>
                  </tr>
                );
              })}
            </Table>

            <div className="mt-4 flex flex-wrap items-baseline gap-x-6 gap-y-1 border-t border-slate-100 pt-3 text-sm">
              <span className="flex items-baseline gap-2">
                <span className="text-slate-500">{t("hold.count")}</span>
                <span className="font-medium tabular-nums text-slate-900">
                  {formatQuantity(filtered.length, lang, 0)}
                </span>
              </span>
              <span className="flex items-baseline gap-2">
                <span className="text-slate-500">{t("hold.total")}</span>
                <span className="font-medium tabular-nums text-slate-900">
                  {formatMoney(totalBase, base, lang)}
                </span>
              </span>
            </div>
          </>
        )}
      </Card>

      {/* Below the positions, because it is the other half of the same story:
          what is still held, and what was closed and is no longer in that
          table at all. */}
      <SoldPositions onDelete={(sale) => setSaleToDelete(sale)} />

      {formOpen && (
        <PositionForm
          asset={editing}
          onSaved={(saved) => setCashNotice(saved.cash)}
          onClose={() => {
            setFormOpen(false);
            setEditing(null);
          }}
        />
      )}

      {selling !== null && (
        <SellForm
          asset={selling}
          onClose={() => setSelling(null)}
          onSold={(sale) => {
            setSelling(null);
            setJustSold(sale);
            setCashNotice(sale.cash);
          }}
        />
      )}

      {deleteTarget !== null && (
        <Modal
          open
          title={t("hold.delete_title")}
          onClose={() => setDeleteTarget(null)}
          footer={
            <>
              <Button
                onClick={() => setDeleteTarget(null)}
                disabled={busyId !== null}
              >
                {t("action.cancel")}
              </Button>
              <Button
                variant="danger"
                loading={busyId === deleteTarget.id}
                onClick={() => {
                  void onDelete();
                }}
              >
                {t("hold.delete_action")}
              </Button>
            </>
          }
        >
          <p>{t("hold.delete_confirm", { symbol: deleteTarget.symbol })}</p>
        </Modal>
      )}

      {saleToDelete !== null && (
        <Modal
          open
          title={t("hold.delete_sale_title")}
          onClose={() => setSaleToDelete(null)}
          footer={
            <>
              <Button onClick={() => setSaleToDelete(null)}>
                {t("action.cancel")}
              </Button>
              <Button
                variant="danger"
                onClick={() => {
                  void onDeleteSale();
                }}
              >
                {t("hold.delete_sale_action")}
              </Button>
            </>
          }
        >
          <p>
            {t("hold.delete_sale_confirm", {
              symbol: saleToDelete.symbol,
              date: formatDate(saleToDelete.sold_on, lang),
            })}
          </p>
        </Modal>
      )}
    </div>
  );
}

export default Holdings;
