/**
 * Gold: Vietnamese, and priced by the shop it would be sold to.
 *
 * The page exists because gold is not a fund and not cash. Its price is not
 * the world price either — SJC bars and rings carry a domestic premium — so
 * what it reads is a Vietnamese goldshop's own published list, normalised to a
 * price per chỉ.
 *
 * Three things the layout has to make impossible to misread:
 *
 * 1. **The shop quotes per unit, and the unit is inside the product's name.**
 *    So the page always shows both figures: what the shop published for its
 *    product line, and that figure expressed for one unit of the unit held.
 *    Showing only the first invites multiplying it by a weight in the wrong
 *    unit, which is a factor of ten.
 * 2. **A shop buys at one price and sells at another.** A holding says which
 *    one it uses, and the page shows the spread, because that gap is a real
 *    cost rather than a rounding error.
 * 3. **A product line can vanish.** When the shop stops publishing one, the
 *    holding is reported as unpriced and left out of the total. Re-pointing it
 *    at another line would be valuing it wrongly and saying nothing.
 */

import { useEffect, useState } from "react";

import {
  createGold,
  deleteGold,
  listGoldProducts,
  updateGold,
} from "../api/client";
import type {
  GoldHolding,
  GoldInput,
  GoldPricing,
  GoldProduct,
  GoldUnit,
  Lang,
} from "../api/types";
import {
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

const UNITS: GoldUnit[] = ["chi", "luong", "gram", "ounce"];
const PRICINGS: GoldPricing[] = ["buy", "sell"];

/** Reads an amount in the reader's own number format. */
function parseAmount(text: string, lang: Lang): number | null {
  const cleaned = text.replace(/[\s\u00a0]/g, "").replace(/[^\d.,-]/g, "");
  if (!cleaned) return null;
  const grouping = lang === "vi" ? /\.(?=\d{3}(\D|$))/g : /,(?=\d{3}(\D|$))/g;
  const decimal = lang === "vi" ? "," : ".";
  const value = Number(cleaned.replace(grouping, "").replace(decimal, "."));
  return Number.isFinite(value) ? value : null;
}

function messageOf(cause: unknown): string {
  return cause instanceof Error ? cause.message : String(cause);
}

/**
 * The goldshop's lines, with the shop's own prices.
 *
 * Fetched once when the form opens rather than on every keystroke: this is one
 * request to a third party, and the list changes a few times a day.
 */
function useGoldProducts() {
  const [products, setProducts] = useState<GoldProduct[] | null>(null);
  const [degraded, setDegraded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void listGoldProducts()
      .then((answer) => {
        if (cancelled) return;
        setProducts(answer.products);
        setDegraded(answer.degraded);
        setError(answer.error);
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        setProducts([]);
        setDegraded(true);
        setError(messageOf(cause));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { products, degraded, error };
}

function GoldForm({
  holding,
  onClose,
}: {
  holding: GoldHolding | null;
  onClose: () => void;
}) {
  const { t, lang } = useI18n();
  const app = useApp();
  const { products, degraded, error: shopError } = useGoldProducts();

  const [name, setName] = useState(holding?.name ?? "");
  const [productKey, setProductKey] = useState(holding?.product_key ?? "");
  const [quantity, setQuantity] = useState(
    holding ? String(holding.quantity) : "",
  );
  const [unit, setUnit] = useState<GoldUnit>(holding?.unit ?? "chi");
  const [pricing, setPricing] = useState<GoldPricing>(holding?.pricing ?? "buy");
  const [costBasis, setCostBasis] = useState(
    holding?.cost_basis === null || holding?.cost_basis === undefined
      ? ""
      : String(holding.cost_basis),
  );
  const [note, setNote] = useState(holding?.note ?? "");
  const [query, setQuery] = useState("");
  const [attempted, setAttempted] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // The first line is chosen for a new holding so the form is never in a state
  // that cannot be saved: SJC first, which is what most people mean.
  useEffect(() => {
    if (holding === null && productKey === "" && products && products.length > 0) {
      const sjc = products.find((product) => product.key.includes("sjc"));
      setProductKey((sjc ?? products[0]).key);
    }
  }, [products, productKey, holding]);

  const needle = query.trim().toLowerCase();
  const shown = (products ?? []).filter(
    (product) =>
      needle === "" ||
      product.name.toLowerCase().includes(needle) ||
      product.key.includes(needle),
  );
  const chosen = (products ?? []).find((product) => product.key === productKey) ?? null;

  const amount = parseAmount(quantity, lang);
  const cost = costBasis.trim() === "" ? null : parseAmount(costBasis, lang);

  const submit = async () => {
    setAttempted(true);
    if (!name.trim() || amount === null || amount <= 0 || productKey === "") return;
    setSaving(true);
    setError(null);

    const body: GoldInput = {
      name: name.trim(),
      currency: "VND",
      quantity: amount,
      unit,
      product_key: productKey,
      pricing,
      cost_basis: cost,
      note: note.trim() || null,
    };

    try {
      if (holding) {
        await updateGold(holding.id, body);
      } else {
        await createGold(body);
      }
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
      title={holding ? t("gold.edit_title") : t("gold.add")}
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
        {degraded && (
          <Notice tone="warning" title={t("gold.shop_down")}>
            {t("gold.shop_down_hint")}
            {shopError && <span className="block">{shopError}</span>}
          </Notice>
        )}

        <Input
          autoFocus
          label={t("gold.holding")}
          placeholder="SJC 5 chỉ"
          value={name}
          onChange={(event) => setName(event.target.value)}
          error={attempted && !name.trim() ? t("form.required") : undefined}
        />

        <Input
          label={t("gold.search_products")}
          hint={t("gold.product_hint")}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />

        <Select
          label={t("gold.product")}
          value={productKey}
          onChange={(event) => setProductKey(event.target.value)}
          error={attempted && productKey === "" ? t("form.required") : undefined}
        >
          {shown.length === 0 && <option value="">{t("gold.no_products")}</option>}
          {shown.map((product) => (
            <option key={product.key} value={product.key}>
              {product.name} — {formatMoney(product.buy, "VND", lang)}/
              {t("gold.unit.chi")}
            </option>
          ))}
        </Select>

        {chosen && (
          <div className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
            <div className="flex flex-wrap justify-between gap-2">
              <span>{t("gold.pricing.buy")}</span>
              <span className="tabular-nums font-medium text-slate-900">
                {formatMoney(chosen.buy, "VND", lang)}
              </span>
            </div>
            <div className="mt-1 flex flex-wrap justify-between gap-2">
              <span>{t("gold.pricing.sell")}</span>
              <span className="tabular-nums font-medium text-slate-900">
                {formatMoney(chosen.sell, "VND", lang)}
              </span>
            </div>
            <p className="mt-1 text-slate-500">
              {t("gold.price_date")}: {formatDate(chosen.updated_on, lang)}
            </p>
          </div>
        )}

        <div className="grid grid-cols-2 gap-3">
          <NumberInput
            label={t("gold.quantity")}
            value={quantity}
            onValueChange={setQuantity}
            error={
              attempted && (amount === null || amount <= 0)
                ? t("form.required")
                : undefined
            }
          />
          <Select
            label={t("gold.unit")}
            value={unit}
            onChange={(event) => {
              const next = UNITS.find((code) => code === event.target.value);
              if (next) setUnit(next);
            }}
          >
            {UNITS.map((code) => (
              <option key={code} value={code}>
                {t(`gold.unit.${code}` as const)}
              </option>
            ))}
          </Select>
        </div>

        <Select
          label={t("gold.pricing")}
          hint={t("gold.pricing_hint")}
          value={pricing}
          onChange={(event) => {
            const next = PRICINGS.find((code) => code === event.target.value);
            if (next) setPricing(next);
          }}
        >
          {PRICINGS.map((code) => (
            <option key={code} value={code}>
              {t(`gold.pricing.${code}` as const)}
            </option>
          ))}
        </Select>

        <NumberInput
          label={`${t("gold.cost")} (${t("state.optional")})`}
          value={costBasis}
          onValueChange={setCostBasis}
        />

        <Textarea
          label={`${t("form.note")} (${t("state.optional")})`}
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />
      </div>
    </SlideOver>
  );
}

export function Gold() {
  const { t, lang } = useI18n();
  const app = useApp();

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<GoldHolding | null>(null);
  const [removing, setRemoving] = useState<GoldHolding | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const portfolio = app.portfolio;
  if (!portfolio) return <Spinner label={t("state.loading")} />;

  const base = app.baseCurrency;
  const rows = portfolio.gold;

  // One notice for the whole page rather than one per holding: when the shop
  // is unreachable every holding is unpriced for the same reason.
  const shopDown = rows.some((row) => row.reason === "price_list_unreachable");
  const goneProducts = rows.filter((row) => row.reason === "no_shop_price");

  const totalWeight = rows.reduce((sum, row) => sum + row.quantity, 0);
  const totalCost = rows.reduce((sum, row) => sum + (row.cost_basis ?? 0), 0);

  const confirmDelete = async () => {
    if (removing === null) return;
    setBusy(true);
    try {
      await deleteGold(removing.id);
      await app.refresh();
      setRemoving(null);
      setError(null);
    } catch (cause) {
      setError(messageOf(cause));
    } finally {
      setBusy(false);
    }
  };

  /** The value of one holding minus what it cost, in the holding's currency. */
  const gainOf = (row: GoldHolding): { gain: number; pct: number } | null => {
    if (row.value === null || row.cost_basis === null) return null;
    const gain = row.value - row.cost_basis;
    return { gain, pct: row.cost_basis === 0 ? 0 : (gain / row.cost_basis) * 100 };
  };

  return (
    <div className="space-y-4">
      {error && (
        <Notice tone="error" title={t("form.save_failed")} onDismiss={() => setError(null)}>
          {error}
        </Notice>
      )}

      {shopDown && (
        <Notice tone="warning" title={t("gold.shop_down")}>
          {t("gold.shop_down_hint")}
        </Notice>
      )}

      {goneProducts.length > 0 && (
        <Notice tone="warning" title={t("dash.unconverted")}>
          <ul className="space-y-1">
            {goneProducts.map((row) => (
              <li key={row.id}>
                <span className="font-medium">{row.name}</span> —{" "}
                {t("gold.product_gone")}
              </li>
            ))}
          </ul>
        </Notice>
      )}

      <Card
        title={t("gold.title")}
        subtitle={t("gold.note")}
        actions={
          <Button
            variant="primary"
            onClick={() => {
              setEditing(null);
              setFormOpen(true);
            }}
          >
            {t("gold.add")}
          </Button>
        }
      >
        {rows.length === 0 ? (
          <EmptyState
            title={t("gold.none_title")}
            body={t("gold.none_body")}
            action={
              <Button
                variant="primary"
                onClick={() => {
                  setEditing(null);
                  setFormOpen(true);
                }}
              >
                {t("gold.add")}
              </Button>
            }
          />
        ) : (
          <div className="space-y-3">
            {rows.map((row) => {
              const gain = gainOf(row);
              const counted = row.value_base !== null;
              const unitLabel = t(`gold.unit.${row.unit}` as const);
              return (
                <div
                  key={row.id}
                  className={`rounded-xl border px-4 py-3 ${
                    counted ? "border-slate-200 bg-white" : "border-amber-200 bg-amber-50/50"
                  }`}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium text-slate-900">{row.name}</span>
                        <Badge tone="info">
                          {formatQuantity(row.quantity, lang, 4)} {unitLabel}
                        </Badge>
                        {row.pricing === "sell" ? (
                          <Badge tone="warning">{t("gold.pricing.sell")}</Badge>
                        ) : (
                          <Badge>{t("gold.pricing.buy")}</Badge>
                        )}
                        {!counted && (
                          <Badge tone="warning">{t("state.not_counted")}</Badge>
                        )}
                      </div>
                      <p className="mt-1 text-xs text-slate-500">
                        {row.product_name ?? row.product_key}
                        {row.price_as_of ? ` · ${formatDate(row.price_as_of, lang)}` : ""}
                      </p>
                    </div>

                    <div className="flex shrink-0 gap-1">
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

                  <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                    <Stat
                      // The shop's published figure, named as such, so it is
                      // never multiplied by a weight in another unit.
                      label={t("gold.shop_price")}
                      value={
                        row.shop_price === null
                          ? DASH
                          : formatMoney(row.shop_price, "VND", lang)
                      }
                      hint={t(`gold.pricing.${row.pricing}` as const)}
                    />
                    <Stat
                      label={t("gold.price_per_unit", { unit: unitLabel })}
                      value={row.price === null ? DASH : formatMoney(row.price, "VND", lang)}
                    />
                    <Stat
                      label={t("gold.value")}
                      value={counted ? formatMoney(row.value, "VND", lang) : DASH}
                      hint={
                        counted ? formatMoney(row.value_base, base, lang) : undefined
                      }
                    />
                    <Stat
                      label={t("gold.gain")}
                      value={
                        gain === null
                          ? DASH
                          : formatMoney(gain.gain, "VND", lang)
                      }
                      hint={gain === null ? undefined : formatPercent(gain.pct, lang)}
                      tone={
                        gain === null || gain.gain === 0
                          ? "neutral"
                          : gain.gain > 0
                            ? "positive"
                            : "negative"
                      }
                    />
                  </div>

                  {row.note && (
                    <p className="mt-2 text-xs text-slate-500">{row.note}</p>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {rows.length > 0 && (
        <Card title={t("gold.total")}>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Stat
              label={t("gold.weight")}
              value={`${formatQuantity(totalWeight, lang, 4)} ${t("gold.unit.chi")}`}
              hint={t("gold.source_note")}
            />
            <Stat
              label={t("gold.value")}
              value={formatMoney(portfolio.gold_value, base, lang)}
            />
            {totalCost > 0 && (
              <>
                <Stat label={t("gold.cost")} value={formatMoney(totalCost, "VND", lang)} />
                <Stat
                  label={t("gold.gain")}
                  value={formatMoney(portfolio.gold_value - totalCost, base, lang)}
                  tone={
                    portfolio.gold_value === totalCost
                      ? "neutral"
                      : portfolio.gold_value > totalCost
                        ? "positive"
                        : "negative"
                  }
                />
              </>
            )}
          </div>
        </Card>
      )}

      {formOpen && (
        <GoldForm
          holding={editing}
          onClose={() => {
            setFormOpen(false);
            setEditing(null);
          }}
        />
      )}

      <Modal
        open={removing !== null}
        title={t("gold.delete_confirm", { name: removing?.name ?? "" })}
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
        <p>{t("gold.delete_confirm", { name: removing?.name ?? "" })}</p>
      </Modal>
    </div>
  );
}

export default Gold;
