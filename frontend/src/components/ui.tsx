/**
 * The interface kit: every primitive the app is drawn with.
 *
 * One file, because the alternative in a project this size is a component
 * directory where `Button` has four slightly different definitions and the app
 * looks like four apps. There is one Button, one Card, one Table, and the
 * views compose them.
 *
 * Two conventions the whole kit follows:
 *
 * - **`null` renders as a dash, never as a zero.** `formatMoney` and friends
 *   already do this; the components that take a pre-formatted string simply
 *   print what they are given.
 * - **A tone is a meaning, not a colour.** `tone="negative"` means "this is a
 *   loss" and decides its own colour, so a gain is never green in one view and
 *   red in another.
 */

import {
  forwardRef,
  useEffect,
  useId,
  useMemo,
  useRef,
} from "react";
import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  MouseEvent,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";
import {
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { DASH } from "../i18n";

type Align = "left" | "right" | "center";
type Tone = "neutral" | "positive" | "negative" | "warning" | "info";

const ALIGN: Record<Align, string> = {
  left: "text-left",
  right: "text-right",
  center: "text-center",
};

const TONES: Record<Tone, string> = {
  neutral: "bg-slate-100 text-slate-700 ring-slate-200",
  positive: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  negative: "bg-rose-50 text-rose-700 ring-rose-200",
  warning: "bg-amber-50 text-amber-800 ring-amber-200",
  info: "bg-sky-50 text-sky-700 ring-sky-200",
};

// ---------------------------------------------------------------------------
// Layout
// ---------------------------------------------------------------------------

export function Card({
  title,
  subtitle,
  actions,
  children,
  className = "",
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-2xl border border-slate-200 bg-white shadow-sm ${className}`}
    >
      {(title || actions) && (
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 px-5 py-4">
          <div className="min-w-0">
            {title && (
              <h2 className="text-sm font-semibold tracking-tight text-slate-900">
                {title}
              </h2>
            )}
            {subtitle && (
              <p className="mt-1 max-w-prose text-xs leading-relaxed text-slate-500">
                {subtitle}
              </p>
            )}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className="px-5 py-4">{children}</div>
    </section>
  );
}

export function Stat({
  label,
  value,
  hint,
  tone = "neutral",
}: {
  label: ReactNode;
  value: ReactNode;
  hint?: ReactNode;
  tone?: Tone;
}) {
  const valueTone =
    tone === "positive"
      ? "text-emerald-600"
      : tone === "negative"
        ? "text-rose-600"
        : "text-slate-900";
  return (
    <div className="min-w-0">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
        {label}
      </div>
      <div className={`mt-1 truncate text-2xl font-semibold tabular-nums ${valueTone}`}>
        {value}
      </div>
      {hint && <div className="mt-1 text-xs text-slate-500">{hint}</div>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Controls
// ---------------------------------------------------------------------------

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "ghost" | "danger" | "subtle";
  size?: "sm" | "md";
  loading?: boolean;
};

const VARIANTS: Record<NonNullable<ButtonProps["variant"]>, string> = {
  primary:
    "bg-slate-900 text-white hover:bg-slate-700 disabled:bg-slate-300 disabled:text-slate-500",
  ghost:
    "bg-white text-slate-700 ring-1 ring-inset ring-slate-300 hover:bg-slate-50 disabled:text-slate-400",
  danger:
    "bg-rose-600 text-white hover:bg-rose-500 disabled:bg-rose-200 disabled:text-rose-50",
  subtle: "bg-slate-100 text-slate-700 hover:bg-slate-200 disabled:text-slate-400",
};

export function Button({
  variant = "ghost",
  size = "md",
  loading = false,
  className = "",
  children,
  disabled,
  ...rest
}: ButtonProps) {
  const sizing = size === "sm" ? "px-2.5 py-1 text-xs" : "px-3.5 py-2 text-sm";
  return (
    <button
      type="button"
      {...rest}
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition-colors disabled:cursor-not-allowed ${VARIANTS[variant]} ${sizing} ${className}`}
    >
      {loading && <InlineSpinner />}
      {children}
    </button>
  );
}

export function IconButton({
  label,
  onClick,
  children,
  disabled = false,
  className = "",
}: {
  label: string;
  /** Handed the event so a caller can anchor a menu to the button itself. */
  onClick: (event: MouseEvent<HTMLButtonElement>) => void;
  children: ReactNode;
  disabled?: boolean;
  /** Lets a caller draw the button as a control rather than as bare glyph. */
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
      className={`inline-flex h-7 w-7 items-center justify-center rounded-md text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900 disabled:cursor-not-allowed disabled:text-slate-300 ${className}`}
    >
      {children}
    </button>
  );
}

function FieldShell({
  id,
  label,
  hint,
  error,
  children,
}: {
  id: string;
  label?: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="min-w-0">
      {label && (
        <label
          htmlFor={id}
          className="mb-1 block text-xs font-medium text-slate-700"
        >
          {label}
        </label>
      )}
      {children}
      {error ? (
        <p className="mt-1 text-xs text-rose-600">{error}</p>
      ) : (
        hint && <p className="mt-1 text-xs leading-relaxed text-slate-500">{hint}</p>
      )}
    </div>
  );
}

const CONTROL =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-slate-500 focus:ring-2 focus:ring-slate-200 disabled:bg-slate-50 disabled:text-slate-400";

export const Input = forwardRef<
  HTMLInputElement,
  InputHTMLAttributes<HTMLInputElement> & {
    label?: ReactNode;
    hint?: ReactNode;
    error?: ReactNode;
  }
>(function Input({ label, hint, error, className = "", ...rest }, ref) {
  const generated = useId();
  const id = rest.id ?? generated;
  return (
    <FieldShell id={id} label={label} hint={hint} error={error}>
      <input ref={ref} {...rest} id={id} className={`${CONTROL} ${className}`} />
    </FieldShell>
  );
});

/**
 * A numeric field whose value is a STRING.
 *
 * That is not a shortcut: a number input that stores a `number` cannot
 * represent "1." or "-" while they are being typed, so the field either fights
 * the person using it or silently turns a half-typed amount into 0.
 */
export function NumberInput({
  label,
  hint,
  error,
  value,
  onValueChange,
  className = "",
  ...rest
}: Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange"> & {
  label?: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  value: string;
  onValueChange: (value: string) => void;
}) {
  const generated = useId();
  const id = rest.id ?? generated;
  return (
    <FieldShell id={id} label={label} hint={hint} error={error}>
      <input
        {...rest}
        id={id}
        value={value}
        onChange={(event) => onValueChange(event.target.value)}
        inputMode="decimal"
        autoComplete="off"
        className={`${CONTROL} tabular-nums ${className}`}
      />
    </FieldShell>
  );
}

/**
 * A dropdown with a chevron that sits where it is put.
 *
 * The native arrow cannot be positioned: every browser draws it hard against
 * the control's right edge, whatever padding the control has, so a select whose
 * text starts 12px from the left ends with its arrow touching the border on the
 * right. `appearance: none` removes it and the chevron below is drawn instead,
 * with room on both sides — which is the only way to make the two ends match.
 */
export function Select({
  label,
  hint,
  error,
  className = "",
  children,
  ...rest
}: SelectHTMLAttributes<HTMLSelectElement> & {
  label?: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
}) {
  const generated = useId();
  const id = rest.id ?? generated;
  return (
    <FieldShell id={id} label={label} hint={hint} error={error}>
      <div className="relative">
        <select
          {...rest}
          id={id}
          className={`${CONTROL} cursor-pointer appearance-none pr-10 ${className}`}
        >
          {children}
        </select>
        <svg
          aria-hidden="true"
          viewBox="0 0 20 20"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.75"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="pointer-events-none absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500"
        >
          <path d="M5.5 8l4.5 4.5L14.5 8" />
        </svg>
      </div>
    </FieldShell>
  );
}

export function Textarea({
  label,
  hint,
  error,
  className = "",
  ...rest
}: TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label?: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
}) {
  const generated = useId();
  const id = rest.id ?? generated;
  return (
    <FieldShell id={id} label={label} hint={hint} error={error}>
      <textarea
        {...rest}
        id={id}
        rows={rest.rows ?? 2}
        className={`${CONTROL} resize-y ${className}`}
      />
    </FieldShell>
  );
}

export function Badge({
  tone = "neutral",
  children,
}: {
  tone?: Tone;
  children: ReactNode;
}) {
  return (
    <span
      // A pill is one line by definition. Wrapped, the second line spills out
      // of the rounded ends and the badge stops reading as a badge; a wider
      // column scrolls inside the table, which is the smaller price.
      className={`inline-flex items-center whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${TONES[tone]}`}
    >
      {children}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Tables
// ---------------------------------------------------------------------------

export function Table({ head, children }: { head: ReactNode; children: ReactNode }) {
  return (
    <div className="-mx-5 overflow-x-auto px-5">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-slate-200">{head}</tr>
        </thead>
        <tbody className="divide-y divide-slate-100">{children}</tbody>
      </table>
    </div>
  );
}

export function Th({
  children,
  align = "left",
}: {
  children?: ReactNode;
  align?: Align;
}) {
  return (
    <th
      scope="col"
      className={`whitespace-nowrap px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500 ${ALIGN[align]}`}
    >
      {children}
    </th>
  );
}

export function Td({
  children,
  align = "left",
  className = "",
}: {
  children?: ReactNode;
  align?: Align;
  className?: string;
}) {
  return (
    <td
      className={`px-3 py-2.5 align-middle text-slate-700 ${ALIGN[align]} ${className}`}
    >
      {children}
    </td>
  );
}

// ---------------------------------------------------------------------------
// Feedback
// ---------------------------------------------------------------------------

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-slate-500">
      <InlineSpinner />
      {label}
    </div>
  );
}

function InlineSpinner() {
  return (
    <span
      aria-hidden="true"
      className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent"
    />
  );
}

export function EmptyState({
  title,
  body,
  action,
}: {
  title: ReactNode;
  body?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50/60 px-5 py-8 text-center">
      <p className="text-sm font-medium text-slate-700">{title}</p>
      {body && (
        <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-slate-500">
          {body}
        </p>
      )}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  );
}

export function Notice({
  tone = "info",
  title,
  children,
  onDismiss,
}: {
  tone?: "warning" | "error" | "info";
  title?: ReactNode;
  children: ReactNode;
  onDismiss?: () => void;
}) {
  const palette =
    tone === "error"
      ? "border-rose-200 bg-rose-50 text-rose-800"
      : tone === "warning"
        ? "border-amber-200 bg-amber-50 text-amber-900"
        : "border-sky-200 bg-sky-50 text-sky-900";
  return (
    <div className={`rounded-xl border px-4 py-3 text-xs leading-relaxed ${palette}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          {title && <p className="mb-1 text-sm font-semibold">{title}</p>}
          <div>{children}</div>
        </div>
        {onDismiss && (
          <button
            type="button"
            onClick={onDismiss}
            className="shrink-0 text-current opacity-60 hover:opacity-100"
            aria-label="dismiss"
          >
            ×
          </button>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Overlays
// ---------------------------------------------------------------------------

export function Modal({
  open,
  title,
  onClose,
  children,
  footer,
}: {
  open: boolean;
  title: ReactNode;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <Overlay open={open} onClose={onClose} side="center">
      <div className="w-full max-w-lg rounded-2xl bg-white shadow-xl">
        <header className="flex items-center justify-between border-b border-slate-100 px-5 py-3">
          <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
          <IconButton label="close" onClick={onClose}>
            ×
          </IconButton>
        </header>
        <div className="max-h-[70vh] overflow-y-auto px-5 py-4">{children}</div>
        {footer && (
          <footer className="flex justify-end gap-2 border-t border-slate-100 px-5 py-3">
            {footer}
          </footer>
        )}
      </div>
    </Overlay>
  );
}

export function SlideOver({
  open,
  title,
  onClose,
  children,
  footer,
}: {
  open: boolean;
  title: ReactNode;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <Overlay open={open} onClose={onClose} side="right">
      <div className="flex h-full w-full max-w-md flex-col bg-white shadow-2xl">
        <header className="flex items-center justify-between border-b border-slate-100 px-5 py-3">
          <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
          <IconButton label="close" onClick={onClose}>
            ×
          </IconButton>
        </header>
        <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>
        {footer && (
          <footer className="flex justify-end gap-2 border-t border-slate-100 px-5 py-3">
            {footer}
          </footer>
        )}
      </div>
    </Overlay>
  );
}

function Overlay({
  open,
  onClose,
  side,
  children,
}: {
  open: boolean;
  onClose: () => void;
  side: "center" | "right";
  children: ReactNode;
}) {
  const wrapper = useRef<HTMLDivElement>(null);

  // Escape closes, which is what every overlay in every application does and
  // the absence of which is felt immediately.
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    globalThis.addEventListener("keydown", onKey);
    return () => globalThis.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className={`fixed inset-0 z-50 flex bg-slate-900/40 backdrop-blur-sm ${
        side === "center" ? "items-center justify-center p-4" : "justify-end"
      }`}
      onMouseDown={(event) => {
        // A click that lands on the backdrop itself — outside the wrapper —
        // closes, for the strip the wrapper does not cover.
        if (event.target === event.currentTarget) onClose();
      }}
    >
      {/* The wrapper takes the room it is given, and the panel inside decides
          how much of it to use.

          It used to be a bare `div`, which as a flex item is sized by its own
          content — so a panel asking for `w-full max-w-lg` was measured
          against a 229px parent and came out 229px wide, with the `max-w-lg`
          never reached. A dialog a third of the width it asks for looks like a
          mistake, because it is one.

          It carries the alignment too: a wrapper that fills the backdrop
          takes the centring with it, so a `justify-center` left on the outer
          flex would centre the wrapper — which is already the full width — and
          leave the dialog sitting against the left edge.

          And the outside-click test: clicking the dimmed area must still
          close, and clicking the panel must not. */}
      <div
        ref={wrapper}
        className={`flex w-full min-w-0 max-w-full ${
          side === "center" ? "justify-center" : "justify-end"
        }`}
        onMouseDown={(event) => {
          if (event.target === event.currentTarget) onClose();
        }}
      >
        {children}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Charts
// ---------------------------------------------------------------------------

/**
 * Recharts hands a formatter `ValueType | undefined`, so these take `unknown`
 * and coerce: a chart label is not a place to enforce a type, and a tooltip
 * that throws on a missing value is worse than one that prints a dash.
 */
function compactNumber(value: unknown): string {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return DASH;
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(numeric);
}

function compactTick(value: unknown): string {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "";
  return new Intl.NumberFormat(undefined, {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(numeric);
}

/** Deterministic palette, so a kind keeps its colour between renders. */
const SERIES_COLORS = [
  "#0f172a",
  "#0284c7",
  "#f59e0b",
  "#059669",
  "#7c3aed",
  "#e11d48",
  "#0891b2",
  "#65a30d",
];

export function seriesColor(index: number): string {
  return SERIES_COLORS[index % SERIES_COLORS.length];
}

export function AllocationPie({
  slices,
  height = 200,
}: {
  slices: { label: string; value: number; color?: string }[];
  height?: number;
}) {
  // The colour belongs to the slice's place in the FULL list, before empty
  // kinds are dropped, so the legend can name the same colour with the same
  // index and no swatch can point at another kind's slice.
  const coloured = slices.map((slice, index) => ({
    ...slice,
    color: slice.color ?? seriesColor(index),
  }));
  const data = coloured.filter((slice) => slice.value > 0);
  if (data.length === 0) {
    return (
      <div
        className="flex w-full min-w-0 items-center justify-center text-sm text-slate-400"
        style={{ height }}
      >
        {DASH}
      </div>
    );
  }
  return (
    // The wrapper states both of its own dimensions and is allowed to shrink.
    // A chart that measures a parent instead would draw nothing inside a grid
    // cell whose height only exists once its contents have one.
    <div className="w-full min-w-0" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="label"
            innerRadius="55%"
            outerRadius="85%"
            paddingAngle={2}
            stroke="none"
            // Drawn at once rather than swept in: an entry animation is a
            // second of missing chart on a first paint, and a chart that is
            // only correct once the animation has run is a chart that is wrong
            // in every screenshot taken before it finishes.
            isAnimationActive={false}
          >
            {data.map((slice) => (
              <Cell key={slice.label} fill={slice.color} />
            ))}
          </Pie>
          <Tooltip formatter={compactNumber} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

export function Bars({
  bars,
  height = 160,
}: {
  bars: { label: string; value: number }[];
  height?: number;
}) {
  const max = useMemo(
    () => Math.max(...bars.map((bar) => Math.abs(bar.value)), 1),
    [bars],
  );
  return (
    <div className="space-y-2" style={{ minHeight: height / 3 }}>
      {bars.map((bar, index) => (
        <div key={bar.label} className="flex items-center gap-3">
          <div className="w-24 shrink-0 truncate text-xs text-slate-600">
            {bar.label}
          </div>
          <div className="h-3 flex-1 overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full"
              style={{
                width: `${Math.max((Math.abs(bar.value) / max) * 100, 1)}%`,
                backgroundColor: seriesColor(index),
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

export function Sparkline({
  points,
  height = 180,
}: {
  points: { label: string; value: number }[];
  height?: number;
}) {
  if (points.length === 0) {
    return (
      <div
        className="flex items-center justify-center text-sm text-slate-400"
        style={{ height }}
      >
        {DASH}
      </div>
    );
  }
  const values = points.map((point) => point.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const pad = (max - min) * 0.05 || Math.abs(max) * 0.05 || 1;
  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 11, fill: "#64748b" }}
            tickLine={false}
            axisLine={false}
            minTickGap={24}
          />
          <YAxis
            domain={[min - pad, max + pad]}
            tick={{ fontSize: 11, fill: "#64748b" }}
            tickLine={false}
            axisLine={false}
            width={70}
            tickFormatter={compactTick}
          />
          <Tooltip formatter={compactNumber} />
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
  );
}
