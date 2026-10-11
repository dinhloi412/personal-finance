/**
 * Settings: the two choices that change what everything else means, and the
 * two facts the user needs in order to trust the data.
 *
 * The base currency is not a display preference — it is the unit every total
 * is expressed in, and changing it re-expresses all of them. The language is
 * applied through i18n first and stored second, so the click is answered by
 * the page redrawing rather than by a spinner.
 *
 * The about block is here because a local-first app has no account page: the
 * file path *is* the backup, and a user who cannot find it cannot back it up.
 */

import { useState } from "react";

import { wipeData } from "../api/client";
import type { Currency, Lang } from "../api/types";
import { useI18n } from "../i18n";
import { useApp } from "../state/AppContext";
import {
  Badge,
  Button,
  Card,
  Modal,
  Notice,
  Select,
  Spinner,
} from "../components/ui";

export function Settings() {
  const { t, lang, setLang } = useI18n();
  const app = useApp();

  const [busy, setBusy] = useState<"base" | "language" | "wipe" | null>(null);
  const [copied, setCopied] = useState(false);
  const [wiping, setWiping] = useState(false);
  const [wiped, setWiped] = useState<Record<string, number> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const settings = app.settings;
  if (!settings) return <Spinner label={t("state.loading")} />;

  const doWipe = async () => {
    setBusy("wipe");
    setError(null);
    try {
      const report = await wipeData();
      setWiped(report.removed);
      setWiping(false);
      // Everything on every page was just deleted; nothing may keep a stale
      // copy of it.
      await app.refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(null);
    }
  };

  const changeBase = (code: Currency) => {
    setBusy("base");
    void app
      .setBaseCurrency(code)
      .catch(() => undefined)
      .finally(() => setBusy(null));
  };

  const changeLanguage = (code: Lang) => {
    // Applied immediately, so the interface answers in the new language while
    // the server copy is being written; reverted if that write fails.
    setLang(code);
    setBusy("language");
    void app
      .setLanguage(code)
      .catch(() => setLang(lang))
      .finally(() => setBusy(null));
  };

  const copyPath = async () => {
    try {
      await navigator.clipboard.writeText(settings.database_path);
      setCopied(true);
    } catch {
      // Copying is a convenience; the path is on screen either way.
    }
  };

  return (
    <div className="space-y-4">
      <Card
        title={t("set.title")}
        actions={busy && <Badge tone="info">{t("state.saving")}</Badge>}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Select
            label={t("set.base_currency")}
            hint={t("set.base_currency_hint")}
            value={settings.base_currency}
            disabled={busy !== null}
            onChange={(event) => {
              // Looked up in the server's own list rather than cast: what the
              // API accepts and what the dropdown offers stay one list.
              const next = settings.supported_currencies.find(
                (code) => code === event.target.value,
              );
              if (next) changeBase(next);
            }}
          >
            {settings.supported_currencies.map((code) => (
              <option key={code} value={code}>
                {t(`currency.${code}` as const)}
              </option>
            ))}
          </Select>

          <Select
            label={t("set.language")}
            hint={t("set.language_hint")}
            value={lang}
            disabled={busy !== null}
            onChange={(event) => {
              const next = settings.supported_languages.find(
                (code) => code === event.target.value,
              );
              if (next) changeLanguage(next);
            }}
          >
            {settings.supported_languages.map((code) => (
              <option key={code} value={code}>
                {t(`lang.${code}` as const)}
              </option>
            ))}
          </Select>
        </div>
      </Card>

      <Card title={t("set.about")}>
        <dl className="space-y-3 text-sm">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <dt className="text-slate-500">{t("set.version")}</dt>
            <dd className="tabular-nums">{settings.version}</dd>
          </div>
          <div className="space-y-2">
            <dt className="text-slate-500">{t("set.database")}</dt>
            <dd className="flex flex-wrap items-center gap-2">
              <code className="break-all rounded bg-slate-100 px-2 py-1 text-xs">
                {settings.database_path}
              </code>
              <Button size="sm" onClick={() => void copyPath()}>
                {copied ? t("action.copied") : t("action.copy")}
              </Button>
            </dd>
            <p className="text-xs leading-relaxed text-slate-500">
              {t("set.database_hint")}
            </p>
          </div>
        </dl>
      </Card>

      <Card title={t("set.scope")}>
        <div className="space-y-2">
          <p>{t("set.scope_tracks")}</p>
          <p className="text-slate-500">{t("set.scope_does_not")}</p>
        </div>
      </Card>

      <Card
        title={t("set.danger")}
        subtitle={t("set.danger_hint")}
        actions={
          <Button variant="danger" onClick={() => setWiping(true)}>
            {t("set.wipe")}
          </Button>
        }
      >
        {wiped !== null && (
          <p className="text-xs text-slate-500">
            {t("set.wipe_done", {
              count: Object.values(wiped).reduce((sum, n) => sum + n, 0),
            })}
          </p>
        )}
      </Card>

      <Modal
        open={wiping}
        title={t("set.wipe_confirm_title")}
        onClose={() => setWiping(false)}
        footer={
          <>
            <Button onClick={() => setWiping(false)}>{t("action.cancel")}</Button>
            <Button variant="danger" loading={busy === "wipe"} onClick={() => void doWipe()}>
              {t("action.confirm")}
            </Button>
          </>
        }
      >
        <p className="text-sm leading-relaxed text-slate-600">
          {t("set.wipe_confirm_body")}
        </p>
        {error && <Notice tone="error">{error}</Notice>}
      </Modal>
    </div>
  );
}

export default Settings;
