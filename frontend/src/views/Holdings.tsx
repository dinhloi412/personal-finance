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
  priceAsset,
  updateAsset,
} from "../api/client";
import type {
  Asset,
  AssetInput,
  AssetPatch,
  Currency,
  MarketKind,
  UnpricedReason,
} from "../api/types";
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
}: {
  /** The position being edited, or null when adding a new one. */
  asset: Asset | null;
  onClose: () => void;
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
    };

    setSaving(true);
    setError(null);
    try {
      if (asset === null) {
        await createAsset(input);
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
          await updateAsset(asset.id, patch);
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
      await deleteAsset(deleteTarget.id);
      await app.refresh();
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
    setFormOpen(true);
  };

  return (
    <div className="space-y-4">
      {actionError && (
        <Notice tone="error" title={t("state.error")}>
          {actionError}
        </Notice>
      )}

      <Card
        title={t("hold.title")}
        actions={
          <Button size="sm" variant="primary" onClick={openAdd}>
            {t("hold.add")}
          </Button>
        }
      >
        <div className="mb-4 flex flex-wrap items-end gap-3">
          <div className="w-40">
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

      {formOpen && (
        <PositionForm
          asset={editing}
          onClose={() => {
            setFormOpen(false);
            setEditing(null);
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
    </div>
  );
}

export default Holdings;
