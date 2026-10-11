/**
 * The cash side of a trade, in the two places it appears.
 *
 * `CashMoveFields` is what a form shows *before* a trade: the amount, in the
 * pot it will move — which is the pot of the trade's own currency, so there is
 * nothing to pick. `CashMoveNotice` is what a page shows *after* one: what
 * moved, or why nothing did. A feature that quietly edits a balance has to say
 * so in the same breath, and it has to say so even when it decided not to —
 * "nothing happened" and "nothing happened because there is no rate" are
 * different facts.
 *
 * One rule shapes both: **the browser never converts currency.** It does not
 * have to. Cash is one pot per currency, so a trade in dollars moves the dollar
 * pot and a trade in đồng moves the dong one: the amount that moves is the
 * trade's own number, to the last decimal.
 */

import { useEffect, useState } from "react";

import type { CashMoveOut, SkipCode } from "../api/types";
import { formatMoney, useI18n } from "../i18n";
import { useApp } from "../state/AppContext";
import { Notice, NumberInput } from "./ui";

/** The `{name}` a movement is described with: the symbol if there is one, and
 * the holding's name otherwise. */
export function moveName(movement: { symbol: string | null; name: string }): string {
  return movement.symbol || movement.name;
}

/**
 * The amount and the pot it will come out of, for one form.
 *
 * Renders nothing when the cash link is off, or when the trade has no amount to
 * move — a purchase with no cost recorded has nothing to pay for, and showing a
 * dead field would suggest otherwise.
 */
export function CashMoveFields({
  direction,
  amount,
  currency,
  cashAmount,
  onCashAmount,
}: {
  /** Which way the money goes. Decides the label, not the arithmetic: the sign
   * comes from the trade, so a user who types a minus is not obeyed. */
  direction: "out" | "in";
  /** What the trade is worth, in `currency`. Null when it is not known yet. */
  amount: number | null;
  currency: string;
  cashAmount: string;
  onCashAmount: (value: string) => void;
}) {
  const { t, lang } = useI18n();
  const app = useApp();
  const linked = app.settings?.cash_linked ?? false;
  const pots = app.portfolio?.cash ?? [];

  // The pot the server will move, worked out the same way: the trade's own
  // currency, or đồng when there is no pot in it (an EUR-quoted holding).
  const pot =
    pots.find((row) => row.currency.toUpperCase() === currency.toUpperCase()) ??
    pots[0] ??
    null;

  // Pre-filled with what the trade is worth, and it follows the trade until the
  // user edits it. The two are in the same currency, so no rate is involved and
  // the number is exact; the field is editable because what left the bank is a
  // fact only the user has — a fee, or a rate they were given.
  const [edited, setEdited] = useState(false);
  useEffect(() => {
    if (!edited && amount !== null && amount > 0) {
      onCashAmount(String(amount));
    }
  }, [amount, edited, onCashAmount]);

  if (!linked || amount === null || amount <= 0 || pot === null) return null;

  return (
    <div className="space-y-4 rounded-xl border border-slate-200 bg-slate-50/60 p-3">
      {/* Which pot, and what is in it: the one thing a user might want to check
          before agreeing to a trade that moves their money. */}
      <p className="text-xs font-medium text-slate-600">
        {t(direction === "out" ? "move.from" : "move.to")}:{" "}
        <span className="text-slate-900">
          {t("cash.pot", { currency: pot.currency })}
        </span>{" "}
        <span className="text-slate-400">
          {formatMoney(pot.balance, pot.currency, lang)}
        </span>
      </p>

      <NumberInput
        label={t("move.amount", { currency: pot.currency })}
        hint={t("move.amount_hint")}
        value={cashAmount}
        onValueChange={(value) => {
          setEdited(true);
          onCashAmount(value);
        }}
      />
    </div>
  );
}

/**
 * What the cash side did, said plainly.
 *
 * Silence when the link is simply off: that is the user's own setting, and a
 * warning on every trade about a feature they chose not to use is noise. Every
 * *other* way of moving nothing is said out loud, because those are the ones
 * that surprise someone who expected the balance to change.
 */
export function CashMoveNotice({ cash }: { cash: CashMoveOut | null | undefined }) {
  const { t, lang } = useI18n();
  if (!cash) return null;

  if (cash.moved && cash.amount) {
    const outgoing = cash.amount < 0;
    const money = formatMoney(Math.abs(cash.amount), cash.currency ?? "", lang);
    const account = cash.account_name ?? "";
    const after =
      cash.balance === null || cash.balance === undefined
        ? null
        : t("move.balance_after", {
            amount: formatMoney(cash.balance, cash.currency ?? "", lang),
          });
    return (
      <Notice tone="info">
        {outgoing
          ? t("move.done_out", { amount: money, account })
          : t("move.done_in", { amount: money, account })}
        {after ? ` · ${after}` : null}
      </Notice>
    );
  }

  if (!cash.skipped || cash.skipped === "link_off") return null;

  return (
    <Notice tone="warning" title={t("move.skipped")}>
      {t(`move.skip.${cash.skipped}` as `move.skip.${SkipCode}`)}
    </Notice>
  );
}
