/**
 * Choosing what to hold: a search, and a text field that always works.
 *
 * The search is a convenience, never a gate. Every symbol this app can price
 * is a string the user can type, so when the feed is slow, rate-limited or
 * renamed, the answer is a warning and an unchanged field — not a form that
 * cannot be completed.
 *
 * The picker reports two things: the symbol as text (`onChange`, so typing is
 * always allowed) and, when the user chose a suggestion, the whole suggestion
 * (`onPick`), which is what fills in a name, a kind and a currency.
 */

import { useEffect, useRef, useState } from "react";

import { searchSymbols } from "../api/client";
import type { MarketKind, Suggestion } from "../api/types";
import { useT } from "../i18n";
import { Badge, Input, Notice, Spinner } from "./ui";

/** Typing is cheap; searching on every keystroke is not. */
const DEBOUNCE_MS = 350;

export function InstrumentPicker({
  value,
  onChange,
  onPick,
  kind,
  label,
  hint,
  placeholder,
}: {
  value: string;
  onChange: (symbol: string) => void;
  onPick?: (suggestion: Suggestion) => void;
  kind?: MarketKind;
  label?: string;
  hint?: string;
  placeholder?: string;
}) {
  const t = useT();
  const [query, setQuery] = useState(value);
  const [results, setResults] = useState<Suggestion[]>([]);
  const [busy, setBusy] = useState(false);
  const [degraded, setDegraded] = useState(false);
  const [touched, setTouched] = useState(false);
  const [open, setOpen] = useState(false);

  // The last query this component itself sent, so that a value arriving from
  // the parent (an edit form being filled in) is not searched for again.
  const selfSet = useRef(false);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!selfSet.current) setQuery(value);
    selfSet.current = false;
  }, [value]);

  useEffect(() => {
    if (!touched) return undefined;
    const text = query.trim();
    if (text.length < 2) {
      setResults([]);
      setOpen(false);
      return undefined;
    }
    let cancelled = false;
    const timer = globalThis.setTimeout(async () => {
      setBusy(true);
      try {
        const answer = await searchSymbols(text, kind);
        if (cancelled) return;
        setResults(answer.suggestions);
        setDegraded(answer.degraded);
        setOpen(true);
      } catch {
        if (cancelled) return;
        setResults([]);
        setDegraded(true);
        setOpen(true);
      } finally {
        if (!cancelled) setBusy(false);
      }
    }, DEBOUNCE_MS);

    return () => {
      cancelled = true;
      globalThis.clearTimeout(timer);
    };
  }, [query, kind, touched]);

  useEffect(() => {
    const onDocumentClick = (event: MouseEvent) => {
      if (box.current && !box.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    globalThis.document.addEventListener("mousedown", onDocumentClick);
    return () => globalThis.document.removeEventListener("mousedown", onDocumentClick);
  }, []);

  const choose = (suggestion: Suggestion) => {
    selfSet.current = true;
    setQuery(suggestion.symbol);
    onChange(suggestion.symbol);
    onPick?.(suggestion);
    setOpen(false);
  };

  return (
    <div ref={box}>
      <Input
        label={label ?? t("pick.search")}
        hint={hint ?? t("form.symbol_hint")}
        placeholder={placeholder ?? t("pick.placeholder")}
        value={query}
        autoComplete="off"
        spellCheck={false}
        onChange={(event) => {
          selfSet.current = true;
          setTouched(true);
          setQuery(event.target.value);
          // Upper-cased as it is typed: every symbol this app prices is
          // upper-case, and a lower-case one would simply fail to quote.
          onChange(event.target.value.toUpperCase());
        }}
        onFocus={() => setOpen(results.length > 0 || degraded)}
      />

      {open && (
        <div className="mt-1 max-h-64 overflow-y-auto rounded-xl border border-slate-200 bg-white shadow-lg">
          {busy && (
            <div className="px-3 py-2">
              <Spinner label={t("pick.searching")} />
            </div>
          )}

          {degraded && (
            <div className="px-3 py-2">
              <Notice tone="warning">{t("pick.degraded")}</Notice>
            </div>
          )}

          {!busy && results.length === 0 && (
            <div className="px-3 py-2 text-xs text-slate-500">
              {t("pick.no_results")}
            </div>
          )}

          {results.map((suggestion) => (
            <button
              key={suggestion.symbol}
              type="button"
              onClick={() => choose(suggestion)}
              className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left transition-colors hover:bg-slate-50"
            >
              <span className="min-w-0">
                <span className="block text-sm font-medium text-slate-900">
                  {suggestion.symbol}
                </span>
                <span className="block truncate text-xs text-slate-500">
                  {suggestion.name}
                  {suggestion.exchange ? ` · ${suggestion.exchange}` : ""}
                </span>
              </span>
              <span className="flex shrink-0 items-center gap-1">
                {suggestion.kind && <Badge>{suggestion.kind}</Badge>}
                {suggestion.currency && <Badge tone="info">{suggestion.currency}</Badge>}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
